import numpy as np
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
        # Default SAW criteria spec (kode, nama, tipe, bobot) based on provided table
        self.criteria_spec = [
            {"kode": "C1.1", "nama": "Lead Time (CV%)", "tipe": "cost", "bobot": 0.15},
            {"kode": "C1.2", "nama": "Supplier Reliability", "tipe": "benefit", "bobot": 0.20},
            {"kode": "C2.1", "nama": "Holding Cost", "tipe": "cost", "bobot": 0.15},
            {"kode": "C2.2", "nama": "Stockout Cost", "tipe": "cost", "bobot": 0.20},
            {"kode": "C3.1", "nama": "Demand Fluctuation", "tipe": "cost", "bobot": 0.15},
            {"kode": "C3.2", "nama": "Supply Disruption", "tipe": "benefit", "bobot": 0.15},
        ]
    
    def get_data(self):
        """Mengambil data dari database"""
        self.alternatives = Item.query.all()

        if not self.alternatives:
            return False

        # Try to load Criteria from DB and map to spec if present
        db_criteria = {c.kode_kriteria: c for c in Criteria.query.all()} if Criteria.query.count() > 0 else {}

        # Build effective criteria list: prefer DB criteria when codes match, otherwise use spec
        self.criteria = []
        for spec in self.criteria_spec:
            kod = spec['kode']
            if kod in db_criteria:
                c = db_criteria[kod]
                self.criteria.append(c)
            else:
                # Lightweight object to hold spec values so rest of the code can access attributes
                self.criteria.append(type('C', (), {
                    'kode_kriteria': spec['kode'],
                    'nama_kriteria': spec['nama'],
                    'tipe': spec['tipe'],
                    'bobot': spec['bobot'],
                    'id': None
                })())

        return True
    
    def build_decision_matrix(self):
        """Membangun matriks keputusan"""
        n_alternatives = len(self.alternatives)
        n_criteria = len(self.criteria)
        
        self.decision_matrix = np.zeros((n_alternatives, n_criteria))
        
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
                    self.decision_matrix[i, j] = criteria_value.nilai
                else:
                    # Fallbacks: try to derive some metrics from item fields if possible
                    fallback = 0
                    # Example: for supply disruption (C3.2) try mapping existing fields
                    kode = getattr(criteria, 'kode_kriteria', '').lower()
                    if kode.startswith('c3.2'):
                        fallback = getattr(item, 'criticality', 0) or getattr(item, 'status', 0)
                    self.decision_matrix[i, j] = fallback
        
        return self.decision_matrix
    
    def normalize_matrix(self):
        """Normalisasi matriks keputusan"""
        n_alternatives, n_criteria = self.decision_matrix.shape
        self.normalized_matrix = np.zeros((n_alternatives, n_criteria))
        
        for j in range(n_criteria):
            column = self.decision_matrix[:, j]
            criteria = self.criteria[j]
            tipe = getattr(criteria, 'tipe', None) or getattr(criteria, 'type', None) or 'cost'

            # Use robust normalization: benefit => value / max, cost => min / value
            if tipe.lower() == 'benefit':
                max_val = np.max(column)
                if max_val > 0:
                    self.normalized_matrix[:, j] = column / max_val
                else:
                    self.normalized_matrix[:, j] = 0
            else:
                # cost attribute: lower is better
                non_zero = column[column > 0]
                if non_zero.size > 0:
                    min_val = np.min(non_zero)
                    min_val = max(min_val, 1e-9)
                    self.normalized_matrix[:, j] = np.where(column > 0, min_val / column, 0)
                else:
                    self.normalized_matrix[:, j] = 0
        
        return self.normalized_matrix
    
    def calculate_weighted_scores(self):
        """Menghitung nilai preferensi dengan bobot"""
        n_alternatives, n_criteria = self.normalized_matrix.shape
        self.weighted_matrix = np.zeros((n_alternatives, n_criteria))
        
        for j in range(n_criteria):
            weight = getattr(self.criteria[j], 'bobot', None) or getattr(self.criteria[j], 'weight', None)
            # If weight not present (e.g., lightweight spec object), fall back to criteria_spec
            if weight is None:
                weight = self.criteria_spec[j]['bobot']
            self.weighted_matrix[:, j] = self.normalized_matrix[:, j] * weight
        
        # Hitung total skor untuk setiap alternatif
        self.scores = np.sum(self.weighted_matrix, axis=1)
        
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
                'original_values': self.decision_matrix[i].tolist(),
                'normalized_values': self.normalized_matrix[i].tolist(),
                'weighted_values': self.weighted_matrix[i].tolist()
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
                'kode': getattr(c, 'kode_kriteria', getattr(c, 'kode', None)),
                'nama': getattr(c, 'nama_kriteria', getattr(c, 'nama', None)),
                'bobot': getattr(c, 'bobot', None) or self._spec_bobot_for_code(getattr(c, 'kode_kriteria', getattr(c, 'kode', None))),
                'tipe': getattr(c, 'tipe', None) or self._spec_tipe_for_code(getattr(c, 'kode_kriteria', getattr(c, 'kode', None)))
            } for c in self.criteria],
            'decision_matrix': self.decision_matrix.tolist(),
            'normalized_matrix': self.normalized_matrix.tolist(),
            'weighted_matrix': self.weighted_matrix.tolist(),
            'rankings': results,
            'summary': {
                'total_items': len(self.alternatives),
                'total_criteria': len(self.criteria),
                'highest_score': float(np.max(self.scores)),
                'lowest_score': float(np.min(self.scores)),
                'average_score': float(np.mean(self.scores))
            }
        }

    def _spec_bobot_for_code(self, kode):
        for s in self.criteria_spec:
            if s['kode'] == kode:
                return s['bobot']
        return None

    def _spec_tipe_for_code(self, kode):
        for s in self.criteria_spec:
            if s['kode'] == kode:
                return s['tipe']
        return None
    
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
