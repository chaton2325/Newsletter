from __init__ import create_app

app = create_app()

if __name__ == '__main__':
    # On autorise le mode debug pour le développement
    app.run(debug=True, port=9060 , host='0.0.0.0')
