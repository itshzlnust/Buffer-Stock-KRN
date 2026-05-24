from flask import Flask, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from pathlib import Path

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'buffer-stock-inventory-key'
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = Path(app.instance_path) / 'warehouse.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path.as_posix()}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    with app.app_context():
        db.create_all()
    
    return app
