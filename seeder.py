from app import create_app, db
from app.models import Item, Criteria, CriteriaValue, Stock, Usage, PurchaseRequest, CalculationHistory
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import argparse
import csv

app = create_app()

LOCATION_COLUMNS = {
    'Lemari Kaca': 3,
    'Lemari': 4,
    'Rak A': 5,
    'Rak B': 6,
    'Rak C': 7,
    'Rak D': 8,
    'Rak E': 9,
    'Rak F': 10,
    'Rak G': 11,
    'Lantai': 12,
}

CATEGORY_COST_PROXY = {
    'Switch': 95,
    'Network Camera': 90,
    'NVR': 88,
    'UPS': 85,
    'Mini PC': 82,
    'PC': 80,
    'Monitor': 75,
    'HDD Server': 78,
    'HDD': 70,
    'Media Converter': 68,
    'IP-Phone': 65,
}

CATEGORY_CRITICALITY = {
    'Switch': 10,
    'Network Camera': 10,
    'NVR': 10,
    'UPS': 9,
    'HDD Server': 9,
    'Server': 9,
    'Media Converter': 8,
    'IP-Phone': 8,
    'Network Cable': 8,
    'Patch Cord': 8,
    'PoE Injector': 8,
}

BRAND_CANDIDATES = [
    'WESTERN DIGITAL', 'TP-LINK', 'HIKVISION', 'SEAGATE', 'PANDUIT', 'LOGITECH', 'EPSON',
    'CISCO', 'HPE', 'HP', 'DELL', 'SAMSUNG', 'CANON', 'APC', 'UGREEN', 'BAFO', 'YEALINK',
    'FARGO', 'AUTODESK', 'OMADA', 'KINGSTON', 'VGEN', 'NETVIEL', 'PANASONIC', '3M',
    'NACHI', 'JOYKO', 'ZOLA', 'VENTION', 'CORSAIR', 'ENLIGHT', 'UTICON', 'TENDA',
    'BROCO', 'PHILIPS', 'COMMSCOPE', 'TP LINK', 'TPLINK', 'WD', 'NISO', 'MASKO',
    'ENERGIZER', 'ALKALINE', 'MIFA', 'JACK', 'RJ45', 'FANCO', 'INFORCE', 'NETLINE',
    'KEYBOARD', 'MOUSE', 'MONITOR', 'REMOTE'
]


def _to_number(value):
    if value is None:
        return 0.0
    cleaned = str(value).strip().replace(',', '')
    if cleaned in ('', '-', '#N/A'):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_date(value):
    date_str = (value or '').strip()
    if not date_str:
        return None
    for fmt in ('%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _discover_csv_path(filename):
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / filename,
        base_dir.parent / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f'File CSV tidak ditemukan: {filename}')


def _extract_supplier(*texts):
    combined = ' '.join(text for text in texts if text).upper()
    for candidate in BRAND_CANDIDATES:
        if candidate in combined:
            if candidate in ('WD', 'TPLINK', 'TP LINK'):
                return 'WESTERN DIGITAL' if candidate == 'WD' else 'TP-LINK'
            return candidate
    return '-'


def _build_purchase_reason(item):
    nama = item.nama_item.lower()
    kategori = item.kategori.lower()

    if 'hdd server' in kategori:
        if 'baru' in nama:
            return 'Kapasitas penyimpanan server sudah mulai penuh sehingga perlu penambahan unit baru untuk menjaga performa dan backup data.'
        return 'HDD server lama sudah mulai aus atau penuh sehingga perlu penggantian agar penyimpanan dan operasional server tetap stabil.'

    if 'printer cartridge' in kategori or 'printer ink' in kategori:
        return 'Persediaan consumable printer menipis dan perlu diganti agar aktivitas cetak harian tidak terhenti.'

    if 'network cable' in kategori or 'patch cord' in kategori or 'jack module' in kategori or 'face plate' in kategori or 'rj45' in kategori:
        return 'Kebutuhan instalasi dan perawatan jaringan meningkat sehingga perlu stok cadangan untuk pekerjaan lapangan.'

    if 'switch' in kategori or 'poe switch' in kategori or 'router' in kategori or 'poe injector' in kategori or 'media converter' in kategori or 'nvr' in kategori or 'network camera' in kategori:
        return 'Perangkat jaringan dan keamanan perlu stok cadangan untuk mendukung ekspansi, maintenance, dan penggantian unit bermasalah.'

    if 'ups' in kategori or 'power supply' in kategori or 'stop kontak' in kategori:
        return 'Perangkat pendukung daya perlu disiapkan sebagai cadangan untuk menjaga kontinuitas operasional perangkat kerja.'

    if 'memory' in kategori or 'ssd' in kategori or 'hdd' in kategori or 'mini pc' in kategori or 'pc' in kategori or 'monitor' in kategori:
        return 'Perangkat kerja ini dibutuhkan sebagai cadangan atau pengganti karena unit lama sudah tidak optimal atau kapasitasnya sudah penuh.'

    if 'keyboard' in kategori or 'mouse' in kategori or 'ip-phone' in kategori or 'phone' in kategori or 'video conference' in kategori:
        return 'Perangkat kerja ini perlu disediakan sebagai cadangan agar operasional pengguna tetap berjalan saat ada unit yang rusak atau habis pakai.'

    return 'Pengajuan otomatis hasil sinkronisasi transaksi gudang untuk menjaga ketersediaan stok operasional.'


def load_report_data(report_path):
    records = []
    with report_path.open('r', encoding='utf-8-sig', newline='') as file_obj:
        reader = csv.reader(file_obj)
        next(reader, None)
        next(reader, None)

        for row in reader:
            if len(row) < 14:
                continue

            kategori = (row[1] or '').strip()
            nama_item = (row[2] or '').strip()
            if not kategori or not nama_item:
                continue

            locations = {}
            for loc_name, idx in LOCATION_COLUMNS.items():
                qty = _to_number(row[idx] if idx < len(row) else 0)
                if qty > 0:
                    locations[loc_name] = qty

            total_qty = _to_number(row[13] if len(row) > 13 else 0)
            if total_qty <= 0 and locations:
                total_qty = sum(locations.values())

            dominant_location = ''
            if locations:
                dominant_location = max(locations.items(), key=lambda x: x[1])[0]

            records.append({
                'key': (kategori, nama_item),
                'kategori': kategori,
                'nama_item': nama_item,
                'total_qty': total_qty,
                'dominant_location': dominant_location,
            })

    return records


def load_transaction_data(in_out_path):
    grouped = defaultdict(list)
    monthly_in = defaultdict(float)
    monthly_out = defaultdict(float)
    remarks_by_key = defaultdict(set)

    with in_out_path.open('r', encoding='utf-8-sig', newline='') as file_obj:
        reader = csv.reader(file_obj)
        for row in reader:
            if len(row) < 10:
                continue

            try:
                int((row[0] or '').strip())
            except ValueError:
                continue

            kategori = (row[5] or '').strip()
            nama_item = (row[6] or '').strip()
            in_out = (row[3] or '').strip().upper()
            jenis_trans = (row[2] or '').strip().upper()
            qty = _to_number(row[9])
            trans_date = _parse_date(row[1])
            remarks = (row[10] or '').strip()

            if not kategori or not nama_item or in_out not in ('IN', 'OUT'):
                continue
            if qty <= 0 or trans_date is None:
                continue

            key = (kategori, nama_item)
            grouped[key].append({
                'date': trans_date,
                'jenis_trans': jenis_trans,
                'in_out': in_out,
                'qty': qty,
                'remarks': remarks,
            })
            if remarks:
                remarks_by_key[key].add(remarks)

            ym_key = (key, trans_date.year, trans_date.month)
            if in_out == 'IN':
                monthly_in[ym_key] += qty
            else:
                monthly_out[ym_key] += qty

    return grouped, monthly_in, monthly_out, remarks_by_key


def build_metrics(report_records, transactions, monthly_in, monthly_out):
    month_keys = sorted({(year, month) for (_, year, month) in monthly_in.keys()} | {(year, month) for (_, year, month) in monthly_out.keys()})
    if not month_keys:
        now = datetime.now()
        month_keys = [(now.year, m) for m in range(1, 13)]

    metrics = {}
    for rec in report_records:
        key = rec['key']
        trans_list = sorted(transactions.get(key, []), key=lambda x: x['date'])

        total_out = 0.0
        stock_out_frequency = 0
        for year, month in month_keys:
            out_qty = monthly_out.get((key, year, month), 0.0)
            in_qty = monthly_in.get((key, year, month), 0.0)
            total_out += out_qty
            if out_qty > in_qty:
                stock_out_frequency += 1

        avg_demand = total_out / len(month_keys) if month_keys else 0.0

        in_dates = [t['date'] for t in trans_list if t['in_out'] == 'IN' and t['jenis_trans'] != 'SALDO']
        in_dates.sort()
        if len(in_dates) > 1:
            gaps = [(in_dates[idx] - in_dates[idx - 1]).days for idx in range(1, len(in_dates))]
            lead_time = sum(gaps) / len(gaps)
        else:
            lead_time = 30.0

        lead_time = max(1.0, min(60.0, lead_time))
        item_cost_proxy = float(CATEGORY_COST_PROXY.get(rec['kategori'], 50))
        criticality = float(CATEGORY_CRITICALITY.get(rec['kategori'], 6))

        metrics[key] = {
            'avg_demand': int(round(avg_demand)),
            'lead_time': int(round(lead_time)),
            'item_cost_proxy': int(round(item_cost_proxy)),
            'stock_out_frequency': int(stock_out_frequency),
            'criticality': int(round(criticality)),
        }

    return metrics, month_keys


def seed_data(force=False):
    report_csv = _discover_csv_path('IT_Warehouse_2025 - Copy.xlsx - Report.csv')
    in_out_csv = _discover_csv_path('IT_Warehouse_2025 - Copy.xlsx - IN_OUT.csv')

    report_records = load_report_data(report_csv)
    transactions, monthly_in, monthly_out, remarks_by_key = load_transaction_data(in_out_csv)
    metrics, month_keys = build_metrics(report_records, transactions, monthly_in, monthly_out)

    with app.app_context():
        print('Mulai seeding database dari CSV...')

        if not force and Item.query.count() > 0:
            print('Database sudah berisi data. Seeder dilewati karena mode aman aktif.')
            return

        db.session.query(PurchaseRequest).delete()
        db.session.query(Usage).delete()
        db.session.query(Stock).delete()
        db.session.query(CriteriaValue).delete()
        db.session.query(CalculationHistory).delete()
        db.session.query(Item).delete()
        db.session.query(Criteria).delete()
        db.session.commit()
        print('Data lama dihapus.')

        criteria_data = [
            {
                'kode_kriteria': 'C1',
                'nama_kriteria': 'Average Demand (Rata-rata Permintaan)',
                'bobot': 0.25,
                'tipe': 'benefit',
                'keterangan': 'Rata-rata pengeluaran barang per bulan (unit) dari data transaksi OUT',
            },
            {
                'kode_kriteria': 'C2',
                'nama_kriteria': 'Lead Time (Waktu Tunggu)',
                'bobot': 0.20,
                'tipe': 'cost',
                'keterangan': 'Estimasi jarak hari antar transaksi IN non-saldo (hari) - semakin rendah semakin baik',
            },
            {
                'kode_kriteria': 'C3',
                'nama_kriteria': 'Item Cost (Biaya Item)',
                'bobot': 0.15,
                'tipe': 'cost',
                'keterangan': 'Proxy biaya item berbasis kategori barang',
            },
            {
                'kode_kriteria': 'C4',
                'nama_kriteria': 'Stock Out Frequency',
                'bobot': 0.20,
                'tipe': 'benefit',
                'keterangan': 'Jumlah bulan ketika OUT > IN untuk item tersebut',
            },
            {
                'kode_kriteria': 'C5',
                'nama_kriteria': 'Criticality Level',
                'bobot': 0.20,
                'tipe': 'benefit',
                'keterangan': 'Tingkat kritikalitas item berdasarkan kategori infrastruktur',
            },
        ]

        criteria_objects = {}
        for c in criteria_data:
            criteria = Criteria(**c)
            db.session.add(criteria)
            db.session.flush()
            criteria_objects[criteria.kode_kriteria] = criteria
        db.session.commit()

        sorted_records = sorted(report_records, key=lambda x: (x['kategori'].lower(), x['nama_item'].lower()))
        item_by_key = {}
        for idx, rec in enumerate(sorted_records, start=1):
            supplier_name = _extract_supplier(
                rec['nama_item'],
                ' '.join(sorted(remarks_by_key.get(rec['key'], [])))
            )
            item = Item(
                kode_item=f'ITM-{idx:04d}',
                nama_item=rec['nama_item'],
                kategori=rec['kategori'],
                unit='PCS',
                harga=0.0,
                supplier=supplier_name,
                lokasi_rak=rec['dominant_location'] or '-',
            )
            db.session.add(item)
            db.session.flush()
            item_by_key[rec['key']] = item
        db.session.commit()

        usage_rows = 0
        stock_rows = 0
        criteria_rows = 0
        pr_rows = 0

        for rec in sorted_records:
            item = item_by_key[rec['key']]
            metric = metrics.get(rec['key'], {
                'avg_demand': 0.0,
                'lead_time': 30.0,
                'item_cost_proxy': 50.0,
                'stock_out_frequency': 0.0,
                'criticality': 6.0,
            })

            safety_stock = max(1, int(round(metric['avg_demand'] * 0.5)))
            reorder_point = max(safety_stock + 1, int(round(metric['avg_demand'] * 1.2)))
            stock = Stock(
                item_id=item.id,
                quantity=int(round(rec['total_qty'])),
                safety_stock=safety_stock,
                reorder_point=reorder_point,
            )
            db.session.add(stock)
            stock_rows += 1

            criteria_payload = {
                'C1': metric['avg_demand'],
                'C2': metric['lead_time'],
                'C3': metric['item_cost_proxy'],
                'C4': metric['stock_out_frequency'],
                'C5': metric['criticality'],
            }
            for code, value in criteria_payload.items():
                cv = CriteriaValue(item_id=item.id, criteria_id=criteria_objects[code].id, nilai=value)
                db.session.add(cv)
                criteria_rows += 1

            per_item_monthly_out = defaultdict(float)
            for year, month in month_keys:
                out_qty = monthly_out.get((rec['key'], year, month), 0.0)
                if out_qty > 0:
                    per_item_monthly_out[(year, month)] += out_qty

            for (year, month), out_qty in per_item_monthly_out.items():
                usage = Usage(item_id=item.id, tahun=year, bulan=month, quantity_used=int(round(out_qty)))
                db.session.add(usage)
                usage_rows += 1

        sequence = 1
        for rec in sorted_records:
            item = item_by_key[rec['key']]
            trans = transactions.get(rec['key'], [])
            incoming = [t for t in trans if t['in_out'] == 'IN' and t['jenis_trans'] in ('MASUK', 'ADJ +')]
            if not incoming:
                continue

            qty_requested = int(round(sum(t['qty'] for t in incoming)))
            if qty_requested <= 0:
                continue

            first_date = min(t['date'] for t in incoming)
            alasan = _build_purchase_reason(item)

            pr = PurchaseRequest(
                no_pengajuan=f'PR-{first_date.year}-{sequence:04d}',
                tanggal_pengajuan=first_date,
                item_id=item.id,
                quantity_requested=qty_requested,
                alasan_pengajuan=alasan,
                status='Completed',
                approved_by='IT Manager',
                approved_at=datetime.utcnow(),
                keterangan='Dibentuk otomatis saat sinkronisasi data gudang',
            )
            db.session.add(pr)
            sequence += 1
            pr_rows += 1

        db.session.commit()

        print('\nSeeding selesai!')
        print(f'Total item: {len(sorted_records)}')
        print(f'Total stock: {stock_rows}')
        print(f'Total usage: {usage_rows}')
        print(f'Total criteria values: {criteria_rows}')
        print(f'Total purchase requests: {pr_rows}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed database from CSV files')
    parser.add_argument('--force', action='store_true', help='Reset dan impor ulang data dari CSV')
    args = parser.parse_args()
    seed_data(force=args.force)
