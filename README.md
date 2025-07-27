markdown
# 🎤 TTS Tool Vietnamese - Voice Cloning & Text-to-Speech

<p align="center">
  <img src="static/img/logo.png" alt="TTS Tool Vietnamese" width="200">
</p>

<p align="center">
  <strong>Công cụ Clone giọng & Text-to-Speech Tiếng Việt</strong><br>
  Clone giọng nói chỉ với 10 giây audio - 100% Miễn phí
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#demo">Demo</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#api">API</a> •
  <a href="#deployment">Deployment</a>
</p>

---

## ✨ Features

- 🎤 **Voice Cloning** - Clone giọng với chỉ 10 giây audio
- 🔊 **High-Quality TTS** - Sử dụng Microsoft Neural Voices
- 👥 **Multi-User System** - Quản lý người dùng đầy đủ
- 🔐 **Secure** - JWT authentication, password hashing
- 📊 **Admin Panel** - Quản trị hệ thống
- 🚀 **Fast** - Xử lý realtime với Edge TTS
- 💯 **Free** - Hoàn toàn miễn phí, không giới hạn

## 🎬 Demo

Visit: [https://tts-vietnamese.com](https://tts-vietnamese.com)

## 🛠️ Installation

### Quick Start with Docker

```bash
# Clone repository
git clone https://github.com/ngvinhbao/tts-tool-vietnamese.git
cd tts-tool-vietnamese

# Start with Docker Compose
docker-compose up -d

# Visit http://localhost
```

### Manual Installation

```bash
# 1. Clone repository
git clone https://github.com/ngvinhbao/tts-tool-vietnamese.git
cd tts-tool-vietnamese

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment
cp .env.example .env
# Edit .env with your configuration

# 5. Initialize database
flask db init
flask db migrate
flask db upgrade

# 6. Create admin user
flask create-admin

# 7. Run application
python app.py
```

## 📖 Usage

### 1. Register/Login
- Go to homepage
- Click "Đăng ký" to create account
- Login with your credentials

### 2. Clone Your Voice
- Go to "Giọng của tôi"
- Upload audio file (10-300 seconds)
- Wait for training to complete (~30 seconds)

### 3. Create TTS
- Go to "Tạo giọng nói"
- Enter your text
- Select voice (system or your cloned voice)
- Click "Tạo giọng nói"
- Download the audio file

## 🔌 API Documentation

### Authentication

```bash
# Register
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"user1","email":"user1@example.com","password":"password123","full_name":"User One"}'

# Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user1","password":"password123"}'
```

### TTS Synthesis

```bash
# Create TTS with system voice
curl -X POST http://localhost:5000/api/tts/synthesize \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Xin chào","voice_type":"edge_tts","voice_id":"vi-VN-HoaiMyNeural"}'

# Create TTS with cloned voice
curl -X POST http://localhost:5000/api/tts/synthesize \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Xin chào","voice_type":"cloned","voice_id":"1"}'
```

### Voice Profiles

```bash
# Get your voice profiles
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/api/voice-profiles

# Update a voice profile
curl -X PUT http://localhost:5000/api/voice-profiles/1 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"profile_name":"My Voice","is_public":true}'
```

## 🚀 Deployment

### VPS Deployment

```bash
# 1. SSH to your server
ssh user@your-server.com

# 2. Clone repository
git clone https://github.com/ngvinhbao/tts-tool-vietnamese.git
cd tts-tool-vietnamese

# 3. Run setup script
chmod +x deploy.sh
./deploy.sh

# 4. Configure Nginx
sudo cp nginx.conf /etc/nginx/sites-available/tts-vietnamese
sudo ln -s /etc/nginx/sites-available/tts-vietnamese /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 5. Setup SSL with Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

### Cloud Deployment

#### Heroku
```bash
heroku create tts-vietnamese
heroku addons:create heroku-postgresql:hobby-dev
heroku addons:create heroku-redis:hobby-dev
git push heroku main
```

#### AWS/GCP/Azure
See detailed guide in [DEPLOY.md](docs/DEPLOY.md)

## 🔧 Configuration

### Environment Variables

```env
# Required
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/dbname
REDIS_URL=redis://localhost:6379

# Optional
MAX_CONTENT_LENGTH=104857600  # 100MB
MIN_AUDIO_DURATION=10
MAX_AUDIO_DURATION=300
```

### Voice Settings

Edit `config.py` to add more voices or change settings.

## 📊 Admin Panel

Access admin panel at `/admin` (requires admin role)

Features:
- User management
- System statistics
- Voice profile management
- System logs

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

## 👨‍💻 Author

**Nguyễn Vĩnh Bảo**

- Facebook: [fb.com/ngvinhbao14081](https://fb.com/ngvinhbao14081)
- Telegram: [t.me/nvb1408](https://t.me/nvb1408)
- Email: support@tts-vietnamese.com

## 💖 Support

If you find this project useful, please consider supporting:

- 🏦 VPBank: 0567546604
- ₿ Crypto (TRC20): TULbGQbBGLL4VNrUYob7eWJUDup2ixkUT4

## 🙏 Acknowledgments

- Microsoft Edge TTS for neural voices
- Coqui TTS for voice cloning
- Flask community
- All contributors

---

**Made with ❤️ in Vietnam 🇻🇳**
