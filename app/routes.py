from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from app import db
from app.models import Item, Criteria, CriteriaValue, CalculationHistory, Stock, Usage, PurchaseRequest
from app.saw_algorithm import SAWCalculator
import json, csv, io
from datetime import datetime
from sqlalchemy.orm import joinedload

main_bp = Blueprint('main', __name__)

# ==================== DASHBOARD ====================
@main_bp.route('/')
def index():
    total_items = Item.query.count()
    total_criteria = Criteria.query.count()
    total_calculations = CalculationHistory.query.count()
    
    # Get latest calculation
    latest_calc = CalculationHistory.query.order_by(CalculationHistory.tanggal.desc()).first()
    
    # Get items by category
    categories = db.session.query(Item.kategori, db.func.count(Item.id)).group_by(Item.kategori).all()
    
    # Get low stock items
    low_stock_items = db.session.query(Item).join(Stock).filter(
        Stock.quantity <= Stock.safety_stock
    ).order_by(Stock.quantity.asc()).limit(5).all()
    
    # Get pending PR count
    pending_pr = PurchaseRequest.query.filter_by(status='Pending').count()
    approved_pr = PurchaseRequest.query.filter_by(status='Approved').count()
    
    # Get recent PRs
    recent_prs = PurchaseRequest.query.join(Item).order_by(PurchaseRequest.tanggal_pengajuan.desc()).limit(5).all()
    
    # Calculate years for usage filter
    current_year = datetime.now().year
    years = list(range(current_year - 2, current_year + 1))
    
    return render_template('dashboard.html',
                          total_items=total_items,
                          total_criteria=total_criteria,
                          total_calculations=total_calculations,
                          latest_calc=latest_calc,
                          categories=categories,
                          low_stock_items=low_stock_items,
                          low_stock_count=len(low_stock_items),
                          pending_pr=pending_pr,
                          approved_pr=approved_pr,
                          recent_prs=recent_prs,
                          years=years,
                          current_year=current_year)

# ==================== ITEMS ====================
@main_bp.route('/items')
def items():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = Item.query
    
    # Filter
    kategori_filter = request.args.get('kategori')
    search = request.args.get('search')
    
    if kategori_filter:
        query = query.filter_by(kategori=kategori_filter)
    if search:
        query = query.filter(Item.nama_item.ilike(f'%{search}%'))
    
    items = query.options(joinedload(Item.stock_items)).order_by(Item.kode_item).paginate(
        page=page, per_page=per_page, error_out=False)
    
    categories = db.session.query(Item.kategori).distinct().all()
    categories = [c[0] for c in categories]
    
    return render_template('items/index.html', items=items, categories=categories)

@main_bp.route('/items/create', methods=['GET', 'POST'])
def create_item():
    if request.method == 'POST':
        kode = request.form.get('kode_item')
        nama = request.form.get('nama_item')
        kategori = request.form.get('kategori')
        unit = request.form.get('unit', 'PCS')
        supplier = request.form.get('supplier')
        lokasi = request.form.get('lokasi_rak')
        
        # Check duplicate code
        if Item.query.filter_by(kode_item=kode).first():
            flash('Kode item sudah ada!', 'error')
            return redirect(url_for('main.create_item'))
        
        item = Item(
            kode_item=kode,
            nama_item=nama,
            kategori=kategori,
            unit=unit,
            harga=0,
            supplier=supplier,
            lokasi_rak=lokasi
        )
        db.session.add(item)
        db.session.commit()
        
        # Initialize criteria values with default 0
        criteria_list = Criteria.query.all()
        for c in criteria_list:
            cv = CriteriaValue(item_id=item.id, criteria_id=c.id, nilai=0)
            db.session.add(cv)
        db.session.commit()
        
        flash('Item berhasil ditambahkan!', 'success')
        return redirect(url_for('main.items'))
    
    categories = db.session.query(Item.kategori).distinct().all()
    categories = [c[0] for c in categories]
    return render_template('items/create.html', categories=categories)

@main_bp.route('/items/edit/<int:id>', methods=['GET', 'POST'])
def edit_item(id):
    item = Item.query.get_or_404(id)
    
    if request.method == 'POST':
        item.nama_item = request.form.get('nama_item')
        item.kategori = request.form.get('kategori')
        item.unit = request.form.get('unit')
        item.supplier = request.form.get('supplier')
        item.lokasi_rak = request.form.get('lokasi_rak')
        
        db.session.commit()
        flash('Item berhasil diupdate!', 'success')
        return redirect(url_for('main.items'))
    
    categories = db.session.query(Item.kategori).distinct().all()
    categories = [c[0] for c in categories]
    return render_template('items/edit.html', item=item, categories=categories)

@main_bp.route('/items/delete/<int:id>', methods=['POST'])
def delete_item(id):
    item = Item.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Item berhasil dihapus!', 'success')
    return redirect(url_for('main.items'))

# ==================== CRITERIA ====================
@main_bp.route('/criteria')
def criteria():
    criteria_list = Criteria.query.filter_by(parent_id=None).order_by(Criteria.kode_kriteria).all()
    all_criteria = Criteria.query.order_by(Criteria.kode_kriteria).all()

    def get_total_weight(criteria_items):
        return sum(c.bobot for c in criteria_items)

    total_bobot = get_total_weight(all_criteria)

    return render_template('criteria/index.html',
                          criteria_list=criteria_list,
                          all_criteria=all_criteria,
                          total_bobot=total_bobot)

@main_bp.route('/criteria/create', methods=['GET', 'POST'])
def create_criteria():
    if request.method == 'POST':
        kode = request.form.get('kode_kriteria')
        nama = request.form.get('nama_kriteria')
        bobot = request.form.get('bobot')
        tipe = request.form.get('tipe')
        keterangan = request.form.get('keterangan')
        parent_kode = request.form.get('parent_kode') or None

        if Criteria.query.filter_by(kode_kriteria=kode).first():
            flash('Kode kriteria sudah ada!', 'error')
            return redirect(url_for('main.create_criteria'))

        parent = None
        if parent_kode:
            parent = Criteria.query.filter_by(kode_kriteria=parent_kode).first()

        criteria = Criteria(
            kode_kriteria=kode,
            nama_kriteria=nama,
            bobot=float(bobot),
            tipe=tipe,
            keterangan=keterangan,
            parent_id=parent.id if parent else None
        )
        db.session.add(criteria)
        db.session.commit()

        items = Item.query.all()
        for item in items:
            cv = CriteriaValue(item_id=item.id, criteria_id=criteria.id, nilai=0)
            db.session.add(cv)
        db.session.commit()

        flash('Kriteria berhasil ditambahkan!', 'success')
        return redirect(url_for('main.criteria'))

    parent_options = Criteria.query.filter_by(parent_id=None).order_by(Criteria.kode_kriteria).all()
    total_bobot = sum(c.bobot for c in Criteria.query.all())
    return render_template('criteria/create.html', parent_options=parent_options, total_bobot=total_bobot)

@main_bp.route('/criteria/edit/<int:id>', methods=['GET', 'POST'])
def edit_criteria(id):
    criteria = Criteria.query.get_or_404(id)

    if request.method == 'POST':
        criteria.nama_kriteria = request.form.get('nama_kriteria')
        criteria.bobot = float(request.form.get('bobot'))
        criteria.tipe = request.form.get('tipe')
        criteria.keterangan = request.form.get('keterangan')
        parent_kode = request.form.get('parent_kode') or None
        if parent_kode and parent_kode != criteria.kode_kriteria:
            parent = Criteria.query.filter_by(kode_kriteria=parent_kode).first()
            criteria.parent_id = parent.id if parent else None
        else:
            criteria.parent_id = None

        db.session.commit()
        flash('Kriteria berhasil diupdate!', 'success')
        return redirect(url_for('main.criteria'))

    parent_options = Criteria.query.filter(
        (Criteria.parent_id.is_(None)) | (Criteria.id == criteria.parent_id),
        Criteria.id != criteria.id
    ).order_by(Criteria.kode_kriteria).all()
    return render_template('criteria/edit.html', criteria=criteria, parent_options=parent_options)

@main_bp.route('/criteria/delete/<int:id>', methods=['POST'])
def delete_criteria(id):
    criteria = Criteria.query.get_or_404(id)
    db.session.delete(criteria)
    db.session.commit()
    flash('Kriteria berhasil dihapus!', 'success')
    return redirect(url_for('main.criteria'))

@main_bp.route('/criteria/reset', methods=['POST'])
def reset_criteria():
    default_criteria = [
        {'kode_kriteria': 'C1', 'nama_kriteria': 'Average Demand (Rata-rata Permintaan)', 'bobot': 0.25, 'tipe': 'benefit', 'keterangan': 'Rata-rata pengeluaran barang per bulan (unit)'},
        {'kode_kriteria': 'C2', 'nama_kriteria': 'Lead Time (Waktu Tunggu)', 'bobot': 0.20, 'tipe': 'cost', 'keterangan': 'Estimasi hari antar transaksi IN'},
        {'kode_kriteria': 'C3', 'nama_kriteria': 'Item Cost (Biaya Item)', 'bobot': 0.15, 'tipe': 'cost', 'keterangan': 'Proxy biaya item berbasis kategori'},
        {'kode_kriteria': 'C4', 'nama_kriteria': 'Stock Out Frequency', 'bobot': 0.20, 'tipe': 'benefit', 'keterangan': 'Jumlah bulan OUT > IN'},
        {'kode_kriteria': 'C5', 'nama_kriteria': 'Criticality Level', 'bobot': 0.20, 'tipe': 'benefit', 'keterangan': 'Tingkat kritikalitas item'},
    ]
    db.session.query(Criteria).delete()
    db.session.commit()
    for c in default_criteria:
        db.session.add(Criteria(**c))
    db.session.commit()
    flash('Kriteria direset ke default!', 'success')
    return redirect(url_for('main.criteria'))

# ==================== CRITERIA VALUES ====================
@main_bp.route('/criteria-values')
def criteria_values():
    items = Item.query.order_by(Item.kode_item).all()
    criteria_list = Criteria.query.order_by(Criteria.kode_kriteria).all()
    
    # Build value matrix
    value_matrix = {}
    for item in items:
        value_matrix[item.id] = {}
        for c in criteria_list:
            cv = CriteriaValue.query.filter_by(item_id=item.id, criteria_id=c.id).first()
            value_matrix[item.id][c.id] = cv.nilai if cv else 0
    
    return render_template('criteria_values/index.html',
                          items=items,
                          criteria_list=criteria_list,
                          value_matrix=value_matrix)

@main_bp.route('/criteria-values/update', methods=['POST'])
def update_criteria_values():
    item_id = request.form.get('item_id', type=int)
    
    if not item_id:
        flash('Item tidak ditemukan!', 'error')
        return redirect(url_for('main.criteria_values'))
    
    criteria_list = Criteria.query.all()
    
    for c in criteria_list:
        nilai = request.form.get(f'criteria_{c.id}', 0, type=float)
        cv = CriteriaValue.query.filter_by(item_id=item_id, criteria_id=c.id).first()
        
        if cv:
            cv.nilai = nilai
        else:
            cv = CriteriaValue(item_id=item_id, criteria_id=c.id, nilai=nilai)
            db.session.add(cv)
    
    db.session.commit()
    flash('Nilai kriteria berhasil diupdate!', 'success')
    return redirect(url_for('main.criteria_values'))

@main_bp.route('/criteria-values/bulk-update', methods=['POST'])
def bulk_update_criteria_values():
    """Update semua nilai kriteria sekaligus"""
    items = Item.query.all()
    criteria_list = Criteria.query.all()
    
    for item in items:
        for c in criteria_list:
            field_name = f'val_{item.id}_{c.id}'
            nilai = request.form.get(field_name, 0, type=float)
            
            cv = CriteriaValue.query.filter_by(item_id=item.id, criteria_id=c.id).first()
            if cv:
                cv.nilai = nilai
            else:
                cv = CriteriaValue(item_id=item.id, criteria_id=c.id, nilai=nilai)
                db.session.add(cv)
    
    db.session.commit()
    flash('Semua nilai kriteria berhasil diupdate!', 'success')
    return redirect(url_for('main.criteria_values'))

# ==================== SAW CALCULATION ====================
@main_bp.route('/calculation')
def calculation():
    calc = SAWCalculator()
    results = calc.calculate()
    
    if not results:
        flash('Tidak ada data untuk dihitung. Pastikan data item dan kriteria tersedia.', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('calculation/index.html', results=results)

@main_bp.route('/calculation/save', methods=['POST'])
def save_calculation():
    nama = request.form.get('nama_perhitungan')
    keterangan = request.form.get('keterangan')
    
    calc = SAWCalculator()
    results = calc.calculate()
    
    if results:
        history = CalculationHistory(
            nama_perhitungan=nama,
            keterangan=keterangan,
            hasil=json.dumps(results),
            jumlah_item=results['summary']['total_items']
        )
        db.session.add(history)
        db.session.commit()
        flash('Hasil perhitungan berhasil disimpan!', 'success')
    
    return redirect(url_for('main.calculation_history'))

@main_bp.route('/calculation/recommendation')
def buffer_recommendation():
    top_n = request.args.get('top', 10, type=int)
    calc = SAWCalculator()
    recommendations = calc.get_buffer_stock_recommendation(top_n)
    
    if not recommendations:
        flash('Tidak ada data untuk dianalisis.', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('calculation/recommendation.html', 
                          recommendations=recommendations,
                          top_n=top_n)

@main_bp.route('/calculation/history')
def calculation_history():
    history = CalculationHistory.query.order_by(CalculationHistory.tanggal.desc()).all()
    return render_template('calculation/history.html', history=history)

@main_bp.route('/calculation/history/<int:id>')
def view_calculation_history(id):
    history = CalculationHistory.query.get_or_404(id)
    results = json.loads(history.hasil)
    return render_template('calculation/view_history.html', history=history, results=results)

# ==================== STOCK MANAGEMENT ====================
@main_bp.route('/stock')
def stock():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search')
    kategori_filter = request.args.get('kategori')
    
    query = Item.query.join(Stock, Item.id == Stock.item_id, isouter=True)
    
    if search:
        query = query.filter(Item.nama_item.ilike(f'%{search}%'))
    if kategori_filter:
        query = query.filter(Item.kategori == kategori_filter)
    
    items = query.order_by(Item.kode_item).paginate(page=page, per_page=per_page, error_out=False)
    categories = db.session.query(Item.kategori).distinct().all()
    categories = [c[0] for c in categories]
    
    return render_template('stock/index.html', items=items, categories=categories)

@main_bp.route('/stock/update', methods=['POST'])
def update_stock():
    item_id = request.form.get('item_id', type=int)
    quantity = request.form.get('quantity', 0, type=int)
    safety_stock = request.form.get('safety_stock', 0, type=int)
    reorder_point = request.form.get('reorder_point', 0, type=int)
    
    if not item_id:
        flash('Item tidak ditemukan!', 'error')
        return redirect(url_for('main.stock'))
    
    stock = Stock.query.filter_by(item_id=item_id).first()
    if stock:
        stock.quantity = int(quantity)
        stock.safety_stock = int(safety_stock)
        stock.reorder_point = int(reorder_point)
    else:
        stock = Stock(item_id=item_id, quantity=int(quantity), safety_stock=int(safety_stock), reorder_point=int(reorder_point))
        db.session.add(stock)
    
    db.session.commit()
    flash('Stok berhasil diupdate!', 'success')
    return redirect(url_for('main.stock'))

@main_bp.route('/usage')
def usage():
    available_years = [y for (y,) in db.session.query(Usage.tahun).distinct().order_by(Usage.tahun).all()]
    default_year = available_years[-1] if available_years else datetime.now().year
    year = request.args.get('year', default_year, type=int)
    item_id = request.args.get('item_id', type=int)
    
    query = Usage.query.filter_by(tahun=year)
    if item_id:
        query = query.filter_by(item_id=item_id)
    
    usages = query.order_by(Usage.bulan).all()
    items = Item.query.order_by(Item.kode_item).all()
    
    # Calculate total usage per item
    item_usage = {}
    for usage in usages:
        if usage.item_id not in item_usage:
            item_usage[usage.item_id] = 0
        item_usage[usage.item_id] += usage.quantity_used
    
    return render_template('usage/index.html', 
                          usages=usages, 
                          items=items, 
                          year=year, 
                          selected_item=item_id,
                          item_usage=item_usage,
                          years=available_years or [year])

@main_bp.route('/usage/add', methods=['GET', 'POST'])
def add_usage():
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        tahun = request.form.get('tahun', type=int)
        bulan = request.form.get('bulan', type=int)
        quantity = request.form.get('quantity', 0, type=int)
        
        if not item_id:
            flash('Item harus diisi!', 'error')
            return redirect(url_for('main.add_usage'))
        
        usage = Usage(item_id=item_id, tahun=tahun, bulan=bulan, quantity_used=int(quantity))
        db.session.add(usage)
        db.session.commit()
        
        flash('Data pemakaian berhasil ditambahkan!', 'success')
        return redirect(url_for('main.usage'))
    
    items = Item.query.order_by(Item.nama_item).all()
    available_years = [y for (y,) in db.session.query(Usage.tahun).distinct().order_by(Usage.tahun).all()]
    current_year = available_years[-1] if available_years else datetime.now().year
    return render_template('usage/add.html', items=items, current_year=current_year)

# ==================== PURCHASE REQUEST ====================
@main_bp.route('/purchase')
def purchase_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    status_filter = request.args.get('status')
    
    query = PurchaseRequest.query.join(Item)
    if status_filter:
        query = query.filter(PurchaseRequest.status == status_filter)
    
    prs = query.order_by(PurchaseRequest.tanggal_pengajuan.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('purchase/index.html', prs=prs, status_filter=status_filter)

@main_bp.route('/purchase/history')
def purchase_history():
    status_filter = request.args.get('status', '')
    query = PurchaseRequest.query.join(Item)
    if status_filter:
        query = query.filter(PurchaseRequest.status == status_filter)
    prs = query.order_by(PurchaseRequest.tanggal_pengajuan.desc()).paginate(page=1, per_page=999, error_out=False)
    return render_template('purchase/history.html', prs=prs, status_filter=status_filter)

@main_bp.route('/purchase/create', methods=['GET', 'POST'])
def create_purchase():
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        quantity = request.form.get('quantity', 0, type=int)
        alasan = request.form.get('alasan_pengajuan')
        
        if not item_id:
            flash('Item harus diisi!', 'error')
            return redirect(url_for('main.create_purchase'))
        
        # Generate PR number
        last_pr = PurchaseRequest.query.order_by(PurchaseRequest.id.desc()).first()
        if last_pr:
            num = int(last_pr.no_pengajuan.split('-')[-1]) + 1
        else:
            num = 1
        pr_number = f'PR-{datetime.now().year}-{num:04d}'
        
        pr = PurchaseRequest(
            no_pengajuan=pr_number,
            item_id=item_id,
            quantity_requested=int(quantity),
            alasan_pengajuan=alasan
        )
        db.session.add(pr)
        db.session.commit()
        
        flash(f'Pengajuan pembelian {pr_number} berhasil dibuat!', 'success')
        return redirect(url_for('main.purchase_list'))
    
    items = Item.query.order_by(Item.nama_item).all()
    return render_template('purchase/create.html', items=items)

@main_bp.route('/purchase/<int:id>')
def purchase_detail(id):
    pr = PurchaseRequest.query.get_or_404(id)
    return render_template('purchase/detail.html', pr=pr)

@main_bp.route('/purchase/approve/<int:id>', methods=['POST'])
def approve_purchase(id):
    pr = PurchaseRequest.query.get_or_404(id)
    action = request.form.get('action')
    
    if action == 'approve':
        pr.status = 'Approved'
        pr.approved_at = datetime.utcnow()
        pr.approved_by = request.form.get('approved_by', 'Admin')
        flash('Pengajuan pembelian disetujui!', 'success')
    elif action == 'reject':
        pr.status = 'Rejected'
        pr.keterangan = request.form.get('keterangan')
        flash('Pengajuan pembelian ditolak!', 'warning')
    elif action == 'complete':
        pr.status = 'Completed'
        flash('Pengajuan pembelian selesai!', 'success')
    
    db.session.commit()
    return redirect(url_for('main.purchase_list'))

# ==================== EXPORT CSV ====================
@main_bp.route('/export/csv/<type>')
def export_csv(type):
    if type == 'items':
        items = Item.query.all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Kode', 'Nama', 'Kategori', 'Unit', 'Supplier', 'Lokasi Rak'])
        for item in items:
            writer.writerow([item.kode_item, item.nama_item, item.kategori, item.unit, item.supplier or '', item.lokasi_rak or ''])
        filename = f'items_{datetime.now().strftime("%Y%m%d")}.csv'
    
    elif type == 'stock':
        data = Item.query.join(Stock, Item.id == Stock.item_id, isouter=True).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Kode', 'Nama Item', 'Kategori', 'Unit', 'Stok Saat Ini', 'Safety Stock', 'Reorder Point', 'Status'])
        for item in data:
            stock = item.stock_items[0] if item.stock_items else None
            qty = int(stock.quantity) if stock else 0
            safety = int(stock.safety_stock) if stock else 0
            reorder = int(stock.reorder_point) if stock else 0
            status = 'Low Stock' if qty <= safety else ('Reorder' if qty <= reorder else 'Normal')
            writer.writerow([item.kode_item, item.nama_item, item.kategori, item.unit, qty, safety, reorder, status])
        filename = f'stock_{datetime.now().strftime("%Y%m%d")}.csv'
    
    elif type == 'usage':
        year = request.args.get('year', datetime.now().year, type=int)
        usages = db.session.query(Usage, Item).join(Item, Usage.item_id == Item.id).filter(Usage.tahun == year).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Kode Item', 'Nama Item', 'Tahun', 'Bulan', 'Jumlah Pemakaian'])
        for usage, item in usages:
            writer.writerow([item.kode_item, item.nama_item, usage.tahun, usage.bulan, int(usage.quantity_used)])
        filename = f'usage_{year}_{datetime.now().strftime("%Y%m%d")}.csv'
    
    elif type == 'purchase':
        prs = PurchaseRequest.query.join(Item).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['No PR', 'Tanggal', 'Kode Item', 'Nama Item', 'Qty Diminta', 'Status', 'Disetujui Oleh'])
        for pr in prs:
            writer.writerow([pr.no_pengajuan, pr.tanggal_pengajuan.strftime('%Y-%m-%d'), pr.item.kode_item, pr.item.nama_item, int(pr.quantity_requested), pr.status, pr.approved_by or ''])
        filename = f'purchase_{datetime.now().strftime("%Y%m%d")}.csv'
    
    else:
        flash('Tipe export tidak valid!', 'error')
        return redirect(url_for('main.index'))
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

# ==================== EXPORT & STATIC PAGES ====================
@main_bp.route('/export')
def export_page():
    return render_template('export.html')

@main_bp.route('/about')
def about():
    return render_template('about.html')

# ==================== API ENDPOINTS ====================
@main_bp.route('/api/items')
def api_items():
    items = Item.query.all()
    return jsonify([{
        'id': i.id,
        'kode_item': i.kode_item,
        'nama_item': i.nama_item,
        'kategori': i.kategori,
        'unit': i.unit,
        'supplier': i.supplier,
        'lokasi_rak': i.lokasi_rak
    } for i in items])

@main_bp.route('/api/calculation')
def api_calculation():
    calc = SAWCalculator()
    results = calc.calculate()
    return jsonify(results if results else {'error': 'No data available'})
