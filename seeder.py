from app import create_app, db
from app.models import Item, Criteria, CriteriaValue, Stock, Usage, PurchaseRequest
import random
from datetime import datetime, timedelta

app = create_app()

def seed_data():
    with app.app_context():
        print("Mulai seeding database...")
        
        # Clear existing data
        db.session.query(CriteriaValue).delete()
        db.session.query(Item).delete()
        db.session.query(Criteria).delete()
        db.session.commit()
        print("Data lama dihapus.")
        
        # Seed Criteria (Kriteria untuk SAW)
        criteria_data = [
            {
                'kode_kriteria': 'C1',
                'nama_kriteria': 'Average Demand (Rata-rata Permintaan)',
                'bobot': 0.25,
                'tipe': 'benefit',
                'keterangan': 'Rata-rata permintaan item per bulan (unit) - semakin tinggi semakin baik'
            },
            {
                'kode_kriteria': 'C2',
                'nama_kriteria': 'Lead Time (Waktu Tunggu)',
                'bobot': 0.20,
                'tipe': 'cost',
                'keterangan': 'Waktu tunggu pengiriman dari supplier (hari) - semakin rendah semakin baik'
            },
            {
                'kode_kriteria': 'C3',
                'nama_kriteria': 'Item Cost (Biaya Item)',
                'bobot': 0.15,
                'tipe': 'cost',
                'keterangan': 'Biaya per unit item (ribu rupiah) - semakin rendah semakin baik'
            },
            {
                'kode_kriteria': 'C4',
                'nama_kriteria': 'Stock Out Frequency',
                'bobot': 0.20,
                'tipe': 'benefit',
                'keterangan': 'Frekuensi kehabisan stok dalam 6 bulan terakhir - semakin sering semakin perlu buffer'
            },
            {
                'kode_kriteria': 'C5',
                'nama_kriteria': 'Criticality Level',
                'bobot': 0.20,
                'tipe': 'benefit',
                'keterangan': 'Tingkat kepentingan item (1-10) - semakin tinggi semakin kritis'
            }
        ]
        
        criteria_objects = []
        for c in criteria_data:
            criteria = Criteria(**c)
            db.session.add(criteria)
            criteria_objects.append(criteria)
        
        db.session.commit()
        print(f"{len(criteria_objects)} kriteria ditambahkan.")
        
        # Seed Items (Data Dummy Item Warehouse)
        kategori_list = ['Spare Part', 'Raw Material', 'Consumable', 'Safety Equipment', 'Tools']
        supplier_list = ['PT. Industrial Supply', 'PT. Mega Sejahtera', 'CV. Teknik Jaya', 'PT. Sarana Abadi', 'PT. Sumber Utama']
        lokasi_list = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3', 'D1', 'D2', 'D3']
        
        item_names = [
            ('BEARING 6204', 'Spare Part'),
            ('BEARING 6205', 'Spare Part'),
            ('BEARING 6308', 'Spare Part'),
            ('SEAL OIL NBR 50x70x10', 'Spare Part'),
            ('SEAL OIL VITON 40x60x8', 'Spare Part'),
            ('BELT CONVEYOR EP 100', 'Spare Part'),
            ('ROLLER CONVEYOR 4 inch', 'Spare Part'),
            ('COUPLING FLEXIBLE', 'Spare Part'),
            ('GEAR MOTOR 5 HP', 'Spare Part'),
            ('PUMP CENTRIFugal 3 inch', 'Spare Part'),
            ('VALVE GATE 4 inch', 'Spare Part'),
            ('VALVE BALL SS 2 inch', 'Spare Part'),
            ('FILTER OIL 10 micron', 'Consumable'),
            ('FILTER AIR 50 micron', 'Consumable'),
            ('GREASE LITHIUM EP2', 'Consumable'),
            ('OIL HYDRAULIC VG 68', 'Consumable'),
            ('OIL GEAR VG 220', 'Consumable'),
            ('OIL TURBINE VG 32', 'Consumable'),
            ('SOLVENT CLEANER', 'Consumable'),
            ('PAINT EPOXY GREY', 'Consumable'),
            ('THINNER POLYURETHANE', 'Consumable'),
            ('WELDING ROD E7018', 'Consumable'),
            ('GAS OXYGEN', 'Raw Material'),
            ('GAS ACETYLENE', 'Raw Material'),
            ('STEEL PLATE SS304 6mm', 'Raw Material'),
            ('STEEL PIPE SCH 40 4 inch', 'Raw Material'),
            ('STEEL ANGLE 50x50x5', 'Raw Material'),
            ('BOLT M16x50 SS304', 'Raw Material'),
            ('NUT M16 SS304', 'Raw Material'),
            ('WASHER M16 SS304', 'Raw Material'),
            ('HELMET SAFETY', 'Safety Equipment'),
            ('SAFETY SHOES', 'Safety Equipment'),
            ('SAFETY GOGGLES', 'Safety Equipment'),
            ('EAR PLUG', 'Safety Equipment'),
            ('RESPIRATOR MASK', 'Safety Equipment'),
            ('SAFETY GLOVES', 'Safety Equipment'),
            ('HARNESS FULL BODY', 'Safety Equipment'),
            ('WRENCH SET 14 PCS', 'Tools'),
            ('SOCKET SET 24 PCS', 'Tools'),
            ('PIPE WRENCH 18 inch', 'Tools'),
            ('HAMMER BALL PEIN 2 lb', 'Tools'),
            ('SCREWDRIVER SET 6 PCS', 'Tools'),
            ('PLIER SET 3 PCS', 'Tools'),
            ('MEASURING TAPE 5m', 'Tools'),
            ('CALIPER DIGITAL 150mm', 'Tools'),
            ('MULTIMETER DIGITAL', 'Tools'),
            ('PRESSURE GAUGE 0-10 bar', 'Tools'),
            ('TEMPERATURE GAUGE 0-200C', 'Tools'),
        ]
        
        item_objects = []
        for idx, (nama, kategori) in enumerate(item_names, 1):
            kode = f'ITM-{idx:04d}'
            harga = random.randint(50000, 5000000)
            supplier = random.choice(supplier_list)
            lokasi = random.choice(lokasi_list)
            
            item = Item(
                kode_item=kode,
                nama_item=nama,
                kategori=kategori,
                unit='PCS' if kategori != 'Raw Material' else 'KG/PCS',
                harga=harga,
                supplier=supplier,
                lokasi_rak=f'RACK-{lokasi}'
            )
            db.session.add(item)
            item_objects.append(item)
        
        db.session.commit()
        print(f"{len(item_objects)} item ditambahkan.")
        
        # Seed Criteria Values (Nilai untuk setiap item pada setiap kriteria)
        criteria_values = []
        for item in item_objects:
            for criteria in criteria_objects:
                # Generate nilai sesuai tipe kriteria
                if criteria.kode_kriteria == 'C1':  # Average Demand
                    nilai = random.randint(10, 500)
                elif criteria.kode_kriteria == 'C2':  # Lead Time
                    nilai = random.randint(3, 45)
                elif criteria.kode_kriteria == 'C3':  # Item Cost
                    nilai = round(item.harga / 1000, 2)  # Dalam ribuan
                elif criteria.kode_kriteria == 'C4':  # Stock Out Frequency
                    nilai = random.randint(0, 10)
                elif criteria.kode_kriteria == 'C5':  # Criticality Level
                    if 'Spare Part' in item.kategori or 'Raw Material' in item.kategori:
                        nilai = random.randint(6, 10)
                    else:
                        nilai = random.randint(3, 8)
                else:
                    nilai = random.randint(1, 10)
                
                cv = CriteriaValue(
                    item_id=item.id,
                    criteria_id=criteria.id,
                    nilai=nilai
                )
                db.session.add(cv)
                criteria_values.append(cv)
        
        db.session.commit()
        print(f"{len(criteria_values)} nilai kriteria ditambahkan.")
        
        # Seed Stock
        stocks = []
        for item in item_objects:
            qty = random.randint(0, 200)
            safety = random.randint(10, 50)
            reorder = random.randint(20, 100)
            stock = Stock(item_id=item.id, quantity=qty, safety_stock=safety, reorder_point=reorder)
            db.session.add(stock)
            stocks.append(stock)
        
        db.session.commit()
        print(f"{len(stocks)} data stock ditambahkan.")
        
        # Seed Usage (pemakaian 12 bulan terakhir)
        usages = []
        current_year = datetime.now().year
        for item in item_objects:
            for bulan in range(1, 13):
                qty = random.randint(0, 80)
                usage = Usage(item_id=item.id, tahun=current_year, bulan=bulan, quantity_used=qty)
                db.session.add(usage)
                usages.append(usage)
        
        db.session.commit()
        print(f"{len(usages)} data pemakaian ditambahkan.")
        
        # Seed Purchase Requests
        prs = []
        statuses = ['Pending', 'Approved', 'Rejected', 'Completed']
        for item in item_objects[:15]:
            status = random.choice(statuses)
            last_pr = PurchaseRequest.query.order_by(PurchaseRequest.id.desc()).first()
            if last_pr:
                parts = last_pr.no_pengajuan.split('-')
                num = int(parts[-1]) + 1
                pr_number = f'PR-{parts[1]}-{num:04d}'
            else:
                pr_number = f'PR-{current_year}-0001'
            
            pr = PurchaseRequest(
                no_pengajuan=pr_number,
                item_id=item.id,
                quantity_requested=random.randint(10, 100),
                alasan_pengajuan='Pengajuan pembelian untuk buffer stock',
                status=status,
                approved_by='Admin' if status in ['Approved', 'Completed'] else None,
                approved_at=datetime.utcnow() if status in ['Approved', 'Completed'] else None
            )
            db.session.add(pr)
            prs.append(pr)
        
        db.session.commit()
        print(f"{len(prs)} data pengajuan pembelian ditambahkan.")
        
        print("\nSeeding selesai!")
        print(f"Total: {len(criteria_objects)} kriteria, {len(item_objects)} items, {len(criteria_values)} nilai kriteria, {len(stocks)} stock, {len(usages)} usage, {len(prs)} PR")

if __name__ == '__main__':
    seed_data()
