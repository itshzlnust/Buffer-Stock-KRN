from app import create_app

app = create_app()

if __name__ == '__main__':
    import traceback
    try:
        print("Starting Sistem Buffer Stock")
        print("Access: http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
