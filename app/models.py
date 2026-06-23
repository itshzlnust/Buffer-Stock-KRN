from app import db
from datetime import datetime

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    kode_item = db.Column(db.String(50), unique=True, nullable=False)
    nama_item = db.Column(db.String(200), nullable=False)
    kategori = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(50), default='PCS')
    harga = db.Column(db.Float, default=0)
    supplier = db.Column(db.String(200))
    lokasi_rak = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    criteria_values = db.relationship('CriteriaValue', backref='item', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Item {self.kode_item} - {self.nama_item}>'

class Criteria(db.Model):
    __tablename__ = 'criteria'

    id = db.Column(db.Integer, primary_key=True)
    kode_kriteria = db.Column(db.String(50), unique=True, nullable=False)
    nama_kriteria = db.Column(db.String(200), nullable=False)
    bobot = db.Column(db.Float, nullable=False)
    tipe = db.Column(db.String(20), nullable=False)  # 'benefit' atau 'cost'
    keterangan = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('criteria.id'), nullable=True)

    # Relationship
    criteria_values = db.relationship('CriteriaValue', backref='criteria', lazy=True)
    children = db.relationship('Criteria', backref=db.backref('parent', remote_side=[id]), lazy=True)

    def __repr__(self):
        return f'<Criteria {self.kode_kriteria} - {self.nama_kriteria}>'

class CriteriaValue(db.Model):
    __tablename__ = 'criteria_values'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    criteria_id = db.Column(db.Integer, db.ForeignKey('criteria.id'), nullable=False)
    nilai = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('item_id', 'criteria_id', name='unique_item_criteria'),)
    
    def __repr__(self):
        return f'<CriteriaValue Item:{self.item_id} Criteria:{self.criteria_id} = {self.nilai}>'

class Stock(db.Model):
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Float, default=0)
    safety_stock = db.Column(db.Float, default=0)
    reorder_point = db.Column(db.Float, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    item = db.relationship('Item', backref='stock_items', lazy=True)
    
    def __repr__(self):
        return f'<Stock {self.item.kode_item if self.item else self.item_id}: {self.quantity}>'

class Usage(db.Model):
    __tablename__ = 'usages'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    tahun = db.Column(db.Integer, nullable=False)
    bulan = db.Column(db.Integer, nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    item = db.relationship('Item', backref='usages', lazy=True)
    
    def __repr__(self):
        return f'<Usage {self.item.kode_item if self.item else self.item_id}: {self.quantity_used} (Tahun {self.tahun} Bulan {self.bulan})>'

class PurchaseRequest(db.Model):
    __tablename__ = 'purchase_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    no_pengajuan = db.Column(db.String(50), unique=True, nullable=False)
    tanggal_pengajuan = db.Column(db.DateTime, default=datetime.utcnow)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity_requested = db.Column(db.Float, nullable=False)
    alasan_pengajuan = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')  # Pending, Approved, Rejected, Completed
    approved_by = db.Column(db.String(100))
    approved_at = db.Column(db.DateTime)
    keterangan = db.Column(db.Text)
    
    item = db.relationship('Item', backref='purchase_requests', lazy=True)
    
    def __repr__(self):
        return f'<PurchaseRequest {self.no_pengajuan} - {self.item.nama_item if self.item else self.item_id}>'

class CalculationHistory(db.Model):
    __tablename__ = 'calculation_history'
    
    id = db.Column(db.Integer, primary_key=True)
    nama_perhitungan = db.Column(db.String(200), nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    hasil = db.Column(db.Text)
    jumlah_item = db.Column(db.Integer)
    keterangan = db.Column(db.Text)
    
    def __repr__(self):
        return f'<CalculationHistory {self.nama_perhitungan} - {self.tanggal}>'
