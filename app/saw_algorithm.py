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
    
    def get_data(self):
        """Mengambil data dari database"""
        self.alternatives = Item.query.all()
        self.criteria = Criteria.query.order_by(Criteria.id).all()
        
        if not self.alternatives or not self.criteria:
            return False
        
        return True
    
    def build_decision_matrix(self):
        """Membangun matriks keputusan"""
        n_alternatives = len(self.alternatives)
        n_criteria = len(self.criteria)
        
        self.decision_matrix = np.zeros((n_alternatives, n_criteria))
        
        for i, item in enumerate(self.alternatives):
            for j, criteria in enumerate(self.criteria):
                # Cari nilai criteria untuk item ini
                criteria_value = CriteriaValue.query.filter_by(
                    item_id=item.id,
                    criteria_id=criteria.id
                ).first()
                
                if criteria_value:
                    self.decision_matrix[i, j] = criteria_value.nilai
                else:
                    self.decision_matrix[i, j] = 0
        
        return self.decision_matrix
    
    def normalize_matrix(self):
        """Normalisasi matriks keputusan"""
        n_alternatives, n_criteria = self.decision_matrix.shape
        self.normalized_matrix = np.zeros((n_alternatives, n_criteria))
        
        for j in range(n_criteria):
            column = self.decision_matrix[:, j]
            criteria = self.criteria[j]
            
            if criteria.tipe == 'benefit':
                # Benefit: max normalization
                max_val = np.max(column)
                if max_val != 0:
                    self.normalized_matrix[:, j] = column / max_val
                else:
                    self.normalized_matrix[:, j] = 0
            else:  # cost
                # Cost: min normalization
                non_zero_vals = column[column > 0]
                if non_zero_vals.size > 0:
                    min_val = np.min(non_zero_vals)
                    # Hindari pembagian nol untuk nilai cost yang kosong/0.
                    self.normalized_matrix[:, j] = np.where(column > 0, min_val / column, 0)
                else:
                    self.normalized_matrix[:, j] = 0
        
        return self.normalized_matrix
    
    def calculate_weighted_scores(self):
        """Menghitung nilai preferensi dengan bobot"""
        n_alternatives, n_criteria = self.normalized_matrix.shape
        self.weighted_matrix = np.zeros((n_alternatives, n_criteria))
        
        for j in range(n_criteria):
            weight = self.criteria[j].bobot
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
                'id': c.id,
                'kode': c.kode_kriteria,
                'nama': c.nama_kriteria,
                'bobot': c.bobot,
                'tipe': c.tipe
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
