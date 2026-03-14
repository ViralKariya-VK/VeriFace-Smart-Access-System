veriface/
│
├── .env                          # All secrets & config (gitignored)
├── .env.example                  # Template for cloners
├── requirements.txt              # pip installable
├── environment.yml               # conda reproducible env
├── manage.py
├── README.md
│
├── config/                       # Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   │
│   ├── auth/                     # Registration, login, logout
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── forms.py
│   │
│   ├── door/                     # Arduino control, door state
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── arduino.py            # Arduino singleton
│   │
│   ├── recognition/              # Face enrollment + recognition thread
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── engine.py             # InsightFace logic
│   │   └── pipeline.py           # Background thread logic
│   │
│   ├── guest/                    # QR generation + scanning
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── generator.py
│   │   └── scanner.py
│   │
│   ├── camera/                   # Camera stream management
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── manager.py            # CameraManager singleton
│   │
│   └── core/                     # Shared across apps
│       ├── models.py             # All models in one place
│       ├── admin.py
│       └── apps.py               # AppConfig + startup threads
│
├── templates/
│   ├── base.html                 # App shell (header + footer)
│   ├── landing.html
│   ├── auth/
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── verify_device.html
│   │   └── upload_face.html
│   └── app/
│       ├── live_feed.html
│       ├── door_control.html
│       ├── qr_generator.html
│       ├── logs.html
│       └── user.html
│
└── static/
    ├── css/
    ├── js/
    └── icons/