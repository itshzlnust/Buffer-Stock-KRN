import json
from app.models import Item, Criteria, CriteriaValue
from app import db

class SAWCalculator:
    """
    Implementasi metode Simple Additive Weighting (SAW) untuk sistem buffer stock
    """

    def __init__(self):
        self.alternatives = []
        self.criteria = []
        self.decision_matrix = None
        self.normalized_matrix = None
        self.weighted_matrix = None
        self.scores = None

    def get_data(self):
        """Mengambil data dari database"""
        self.alternatives = Item.query.all()

        if not self.alternatives:
            return False

        self.criteria = Criteria.query.filter_by(parent_id=None).order_by(Criteria.kode_kriteria).all()
        if not self.criteria:
            self.criteria = Criteria.query.order_by(Criteria.kode_kriteria).all()

        return True

    def build_decision_matrix(self):
        """Membangun matriks keputusan"""
        n_alternatives = len(self.alternatives)
        n_criteria = len(self.criteria)

        self.decision_matrix = [[0.0 for _ in range(n_criteria)] for _ in range(n_alternatives)]

        for i, item in enumerate(self.alternatives):
            for j, criteria in enumerate(self.criteria):
                # Prefer lookup by criteria.id when present (from DB), otherwise match by kode_kriteria
                criteria_value = None
                if getattr(criteria, 'id', None):
                    criteria_value = CriteriaValue.query.filter_by(
                        item_id=item.id,
                        criteria_id=criteria.id
                    ).first()
                else:
                    # Match by kode_kriteria through join
                    criteria_value = CriteriaValue.query.join(Criteria).filter(
                        Criteria.kode_kriteria == getattr(criteria, 'kode_kriteria', None),
                        CriteriaValue.item_id == item.id
                    ).first()

                if criteria_value:
                    self.decision_matrix[i][j] = criteria_value.nilai
                else:
                    # Fallbacks: try to derive some metrics from item fields if possible
                    fallback = 0
                    # Example: for supply disruption (C3.2) try mapping existing fields
                    kode = getattr(criteria, 'kode_kriteria', '').lower()
                    if kode.startswith('c3.2'):
                        fallback = getattr(item, 'criticality', 0) or getattr(item, 'status', 0)
                    self.decision_matrix[i][j] = fallback

        return self.decision_matrix

    def normalize_matrix(self):
        """Normalisasi matriks keputusan"""
        n_alternatives = len(self.decision_matrix)
        n_criteria = len(self.decision_matrix[0]) if self.decision_matrix else 0
        self.normalized_matrix = [[0.0 for _ in range(n_criteria)] for _ in range(n_alternatives)]

        for j in range(n_criteria):
            column = [self.decision_matrix[i][j] for i in range(n_alternatives)]
            criteria = self.criteria[j]
            tipe = getattr(criteria, 'tipe', None) or getattr(criteria, 'type', None) or 'cost'

            # Use robust normalization: benefit => value / max, cost => min / value
            if tipe.lower() == 'benefit':
                max_val = max(column) if column else 0
                if max_val > 0:
                    for i in range(n_alternatives):
                        self.normalized_matrix[i][j] = column[i] / max_val
                else:
                    for i in range(n_alternatives):
                        self.normalized_matrix[i][j] = 0.0
            else:
                # cost attribute: lower is better
                non_zero = [v for v in column if v > 0]
                if non_zero:
                    min_val = max(min(non_zero), 1e-9)
                    for i in range(n_alternatives):
                        self.normalized_matrix[i][j] = (min_val / column[i]) if column[i] > 0 else 0.0
                else:
                    for i in range(n_alternatives):
                        self.normalized_matrix[i][j] = 0.0

        return self.normalized_matrix

    def calculate_weighted_scores(self):
        """Menghitung nilai preferensi dengan bobot"""
        n_alternatives = len(self.normalized_matrix)
        n_criteria = len(self.normalized_matrix[0]) if self.normalized_matrix else 0
        self.weighted_matrix = [[0.0 for _ in range(n_criteria)] for _ in range(n_alternatives)]

        for j in range(n_criteria):
            weight = getattr(self.criteria[j], 'bobot', None) or getattr(self.criteria[j], 'weight', None)
            # If weight not present (e.g., lightweight spec object), fall back to criteria_spec
            if weight is None:
                weight = self.criteria_spec[j]['bobot']
            for i in range(n_alternatives):
                self.weighted_matrix[i][j] = self.normalized_matrix[i][j] * weight

        # Hitung total skor untuk setiap alternatif
        self.scores = [sum(self.weighted_matrix[i]) for i in range(n_alternatives)]

        return self.scores

    def rank_alternatives(self):
        """Meranking alternatif berdasarkan skor"""
        rankings = []

        for i, item in enumerate(self.alternatives):
            rankings.append({
                'rank': 0,
                'item_id': item.id,
                'kode_item': item.kode_item,
                'nama_item': item.nama_item,
                'kategori': item.kategori,
                'lokasi_rak': item.lokasi_rak,
                'score': float(self.scores[i]),
                'original_values': self.decision_matrix[i],
                'normalized_values': self.normalized_matrix[i],
                'weighted_values': self.weighted_matrix[i]
            })

        # Sort by score (descending)
        rankings.sort(key=lambda x: x['score'], reverse=True)

        # Assign rank
        for i, r in enumerate(rankings):
            r['rank'] = i + 1

        return rankings

    def calculate(self):
        """Menjalankan seluruh perhitungan SAW"""
        if not self.get_data():
            return None

        self.build_decision_matrix()
        self.normalize_matrix()
        self.calculate_weighted_scores()
        results = self.rank_alternatives()

        return {
            'criteria': [{
                'id': getattr(c, 'id', None),
                'kode': getattr(c, 'kode_kriteria', None),
                'nama': getattr(c, 'nama_kriteria', None),
                'bobot': getattr(c, 'bobot', 0),
                'tipe': getattr(c, 'tipe', 'cost')
            } for c in self.criteria],
            'decision_matrix': self.decision_matrix,
            'normalized_matrix': self.normalized_matrix,
            'weighted_matrix': self.weighted_matrix,
            'rankings': results,
            'summary': {
                'total_items': len(self.alternatives),
                'total_criteria': len(self.criteria),
                'highest_score': float(max(self.scores)) if self.scores else 0.0,
                'lowest_score': float(min(self.scores)) if self.scores else 0.0,
                'average_score': float(sum(self.scores) / len(self.scores)) if self.scores else 0.0
            }
        }

    def get_buffer_stock_recommendation(self, top_n=10):
        """Mendapatkan rekomendasi buffer stock"""
        results = self.calculate()
        if not results:
            return None

        recommendations = []
        for r in results['rankings'][:top_n]:
            item = Item.query.get(r['item_id'])
            recommendations.append({
                'rank': r['rank'],
                'kode_item': r['kode_item'],
                'nama_item': r['nama_item'],
                'kategori': r['kategori'],
                'lokasi': r['lokasi_rak'],
                'score': r['score'],
                'rekomendasi_buffer': self._calculate_buffer_amount(item, r['score'])
            })

        return recommendations

    def _calculate_buffer_amount(self, item, score):
        """Menghitung jumlah buffer stock berdasarkan skor"""
        # Logic: semakin tinggi skor, semakin besar buffer yang direkomendasikan
        base_buffer = 10

        # Ambil nilai demand rata-rata jika ada
        demand_value = CriteriaValue.query.join(Criteria).filter(
            CriteriaValue.item_id == item.id,
            Criteria.nama_kriteria.ilike('%average demand%')
        ).first()

        if demand_value:
            demand = demand_value.nilai
            # Buffer = 20% dari demand * score factor
            buffer = int(demand * 0.2 * (score + 0.5))
            return max(buffer, 5)  # Minimum 5 unit

        return int(base_buffer * (score + 0.5))
