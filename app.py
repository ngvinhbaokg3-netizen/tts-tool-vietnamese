from flask import Flask, request, jsonify, send_file, render_template, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import sys
import json
import asyncio
import edge_tts
from datetime import datetime, timedelta
import uuid
import torch
import numpy as np
from pathlib import Path
import librosa
import soundfile as sf
from functools import wraps
import jwt
from flask_migrate import Migrate

# Import TTS engines
try:
    from TTS.api import TTS as CoquiTTS  # Coqui TTS cho voice cloning
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    print("⚠️ Coqui TTS không khả dụng. Cài đặt: pip install TTS")

# Configuration
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///tts_vietnamese.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    OUTPUT_FOLDER = 'outputs'
    VOICE_SAMPLES_FOLDER = 'voice_samples'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-change-in-production'
    JWT_EXPIRATION_DELTA = timedelta(days=7)
    
    # Voice cloning settings
    MIN_AUDIO_DURATION = 10  # seconds
    MAX_AUDIO_DURATION = 300  # 5 minutes
    SUPPORTED_AUDIO_FORMATS = ['wav', 'mp3', 'ogg', 'flac', 'm4a']

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
CORS(app, supports_credentials=True)

# Create directories
for folder in [Config.UPLOAD_FOLDER, Config.OUTPUT_FOLDER, Config.VOICE_SAMPLES_FOLDER, 'logs']:
    os.makedirs(folder, exist_ok=True)

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')  # user, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    voice_profiles = db.relationship('VoiceProfile', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    tts_history = db.relationship('TTSHistory', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_token(self):
        payload = {
            'user_id': self.id,
            'username': self.username,
            'exp': datetime.utcnow() + Config.JWT_EXPIRATION_DELTA
        }
        return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'voice_profiles_count': self.voice_profiles.count(),
            'tts_history_count': self.tts_history.count()
        }

class VoiceProfile(db.Model):
    __tablename__ = 'voice_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    voice_id = db.Column(db.String(100), unique=True, nullable=False)
    
    # Training data
    audio_file_path = db.Column(db.String(500))
    audio_duration = db.Column(db.Float)  # seconds
    sample_rate = db.Column(db.Integer)
    
    # Model data
    model_path = db.Column(db.String(500))
    embeddings_path = db.Column(db.String(500))
    is_trained = db.Column(db.Boolean, default=False)
    training_status = db.Column(db.String(50), default='pending')  # pending, training, completed, failed
    training_progress = db.Column(db.Integer, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Statistics
    usage_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_name': self.profile_name,
            'description': self.description,
            'voice_id': self.voice_id,
            'audio_duration': self.audio_duration,
            'is_trained': self.is_trained,
            'training_status': self.training_status,
            'training_progress': self.training_progress,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_public': self.is_public,
            'is_active': self.is_active,
            'usage_count': self.usage_count
        }

class TTSHistory(db.Model):
    __tablename__ = 'tts_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    voice_type = db.Column(db.String(50))  # edge_tts, google_tts, cloned
    voice_id = db.Column(db.String(100))
    voice_profile_id = db.Column(db.Integer, db.ForeignKey('voice_profiles.id'))
    
    # Output
    output_file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)  # bytes
    duration = db.Column(db.Float)  # seconds
    
    # Settings
    speed = db.Column(db.Float, default=1.0)
    pitch = db.Column(db.Float, default=0.0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    
    # Relationship
    voice_profile = db.relationship('VoiceProfile', backref='tts_history')
    
    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text[:100] + '...' if len(self.text) > 100 else self.text,
            'voice_type': self.voice_type,
            'voice_id': self.voice_id,
            'duration': self.duration,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Load user callback
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# JWT decorator
def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token không tồn tại'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            user = User.query.get(payload['user_id'])
            
            if not user or not user.is_active:
                return jsonify({'error': 'Người dùng không hợp lệ'}), 401
                
            request.current_user = user
            
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token đã hết hạn'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token không hợp lệ'}), 401
            
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    @jwt_required
    def decorated_function(*args, **kwargs):
        if request.current_user.role != 'admin':
            return jsonify({'error': 'Yêu cầu quyền admin'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Voice Cloning Engine
class VoiceCloner:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if COQUI_AVAILABLE:
            # Sử dụng model XTTS cho tiếng Việt
            self.tts_model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        else:
            self.tts_model = None
    
    def validate_audio(self, audio_path):
        """Kiểm tra audio file cho voice cloning"""
        try:
            # Load audio
            audio, sr = librosa.load(audio_path, sr=None)
            duration = len(audio) / sr
            
            # Check duration
            if duration < Config.MIN_AUDIO_DURATION:
                return False, f"Audio quá ngắn. Cần ít nhất {Config.MIN_AUDIO_DURATION} giây"
            
            if duration > Config.MAX_AUDIO_DURATION:
                return False, f"Audio quá dài. Tối đa {Config.MAX_AUDIO_DURATION} giây"
            
            # Check quality (simple SNR check)
            rms = np.sqrt(np.mean(audio**2))
            if rms < 0.01:
                return False, "Chất lượng audio quá thấp"
            
            return True, {"duration": duration, "sample_rate": sr}
            
        except Exception as e:
            return False, f"Lỗi khi xử lý audio: {str(e)}"
    
    def train_voice(self, voice_profile_id):
        """Train voice cloning model"""
        profile = VoiceProfile.query.get(voice_profile_id)
        if not profile:
            return False, "Không tìm thấy voice profile"
        
        try:
            profile.training_status = 'training'
            profile.training_progress = 0
            db.session.commit()
            
            if not self.tts_model:
                profile.training_status = 'failed'
                db.session.commit()
                return False, "TTS model không khả dụng"
            
            # Load reference audio
            audio_path = profile.audio_file_path
            
            # For XTTS, we just need to store the reference audio
            # The model will use it directly during synthesis
            profile.is_trained = True
            profile.training_status = 'completed'
            profile.training_progress = 100
            db.session.commit()
            
            return True, "Huấn luyện thành công"
            
        except Exception as e:
            profile.training_status = 'failed'
            db.session.commit()
            return False, f"Lỗi huấn luyện: {str(e)}"
    
    def synthesize(self, text, voice_profile_id, output_path):
        """Generate speech using cloned voice"""
        profile = VoiceProfile.query.get(voice_profile_id)
        if not profile or not profile.is_trained:
            return False, "Voice profile không sẵn sàng"
        
        try:
            if not self.tts_model:
                return False, "TTS model không khả dụng"
            
            # Generate speech
            self.tts_model.tts_to_file(
                text=text,
                speaker_wav=profile.audio_file_path,
                language="vi",  # Vietnamese
                file_path=output_path
            )
            
            # Update usage stats
            profile.usage_count += 1
            profile.last_used = datetime.utcnow()
            db.session.commit()
            
            return True, output_path
            
        except Exception as e:
            return False, f"Lỗi tổng hợp: {str(e)}"

# Initialize voice cloner
voice_cloner = VoiceCloner()

# Routes - Web Pages
@app.route('/')
def index():
    """Trang chủ"""
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard người dùng"""
    return render_template('dashboard.html')

@app.route('/admin')
@login_required
def admin_panel():
    """Admin panel"""
    if current_user.role != 'admin':
        return "Access denied", 403
    return render_template('admin.html')

# Routes - Authentication
@app.route('/api/register', methods=['POST'])
def register():
    """Đăng ký người dùng mới"""
    data = request.get_json()
    
    # Validate input
    required_fields = ['username', 'email', 'password', 'full_name']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Thiếu trường {field}'}), 400
    
    # Check existing user
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Tên người dùng đã tồn tại'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email đã được sử dụng'}), 400
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        full_name=data['full_name'],
        role='user'
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    # Generate token
    token = user.generate_token()
    
    return jsonify({
        'message': 'Đăng ký thành công',
        'user': user.to_dict(),
        'token': token
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    """Đăng nhập"""
    data = request.get_json()
    
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Vui lòng nhập tên đăng nhập và mật khẩu'}), 400
    
    # Find user by username or email
    user = User.query.filter(
        (User.username == data['username']) | (User.email == data['username'])
    ).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Tên đăng nhập hoặc mật khẩu không đúng'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Tài khoản đã bị khóa'}), 403
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate token
    token = user.generate_token()
    
    return jsonify({
        'message': 'Đăng nhập thành công',
        'user': user.to_dict(),
        'token': token
    }), 200

@app.route('/api/logout', methods=['POST'])
@jwt_required
def logout():
    """Đăng xuất"""
    return jsonify({'message': 'Đăng xuất thành công'}), 200

@app.route('/api/profile', methods=['GET'])
@jwt_required
def get_profile():
    """Lấy thông tin profile"""
    return jsonify({
        'user': request.current_user.to_dict()
    }), 200

@app.route('/api/profile', methods=['PUT'])
@jwt_required
def update_profile():
    """Cập nhật profile"""
    data = request.get_json()
    user = request.current_user
    
    # Update allowed fields
    if 'full_name' in data:
        user.full_name = data['full_name']
    
    if 'email' in data and data['email'] != user.email:
        # Check if email already exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email đã được sử dụng'}), 400
        user.email = data['email']
    
    if 'password' in data:
        user.set_password(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Cập nhật thành công',
        'user': user.to_dict()
    }), 200

# Routes - Voice Profiles
@app.route('/api/voice-profiles', methods=['GET'])
@jwt_required
def get_voice_profiles():
    """Lấy danh sách voice profiles của user"""
    user = request.current_user
    profiles = user.voice_profiles.filter_by(is_active=True).all()
    
    return jsonify({
        'profiles': [p.to_dict() for p in profiles]
    }), 200

@app.route('/api/voice-profiles', methods=['POST'])
@jwt_required
def create_voice_profile():
    """Tạo voice profile mới"""
    if 'audio' not in request.files:
        return jsonify({'error': 'Vui lòng upload file audio'}), 400
    
    audio_file = request.files['audio']
    profile_name = request.form.get('profile_name', 'Voice Profile')
    description = request.form.get('description', '')
    
    # Validate file
    if audio_file.filename == '':
        return jsonify({'error': 'File không hợp lệ'}), 400
    
    # Check file extension
    ext = audio_file.filename.rsplit('.', 1)[1].lower()
    if ext not in Config.SUPPORTED_AUDIO_FORMATS:
        return jsonify({'error': f'Định dạng không hỗ trợ. Chấp nhận: {", ".join(Config.SUPPORTED_AUDIO_FORMATS)}'}), 400
    
    # Save file
    voice_id = str(uuid.uuid4())
    filename = f"{voice_id}.{ext}"
    filepath = os.path.join(Config.VOICE_SAMPLES_FOLDER, filename)
    audio_file.save(filepath)
    
    # Validate audio
    is_valid, result = voice_cloner.validate_audio(filepath)
    if not is_valid:
        os.remove(filepath)
        return jsonify({'error': result}), 400
    
    # Create voice profile
    profile = VoiceProfile(
        user_id=request.current_user.id,
        profile_name=profile_name,
        description=description,
        voice_id=voice_id,
        audio_file_path=filepath,
        audio_duration=result['duration'],
        sample_rate=result['sample_rate']
    )
    
    db.session.add(profile)
    db.session.commit()
    
    # Start training in background
    import threading
    thread = threading.Thread(target=voice_cloner.train_voice, args=(profile.id,))
    thread.start()
    
    return jsonify({
        'message': 'Voice profile đã được tạo và đang huấn luyện',
        'profile': profile.to_dict()
    }), 201

@app.route('/api/voice-profiles/<int:profile_id>', methods=['DELETE'])
@jwt_required
def delete_voice_profile(profile_id):
    """Xóa voice profile"""
    profile = VoiceProfile.query.get_or_404(profile_id)
    
    # Check ownership
    if profile.user_id != request.current_user.id and request.current_user.role != 'admin':
        return jsonify({'error': 'Không có quyền xóa profile này'}), 403
    
    # Soft delete
    profile.is_active = False
    db.session.commit()
    
    # Optional: Delete files
    if request.args.get('permanent') == 'true':
        if profile.audio_file_path and os.path.exists(profile.audio_file_path):
            os.remove(profile.audio_file_path)
        
        db.session.delete(profile)
        db.session.commit()
    
    return jsonify({'message': 'Đã xóa voice profile'}), 200

# Routes - TTS
@app.route('/api/tts/synthesize', methods=['POST'])
@jwt_required
def synthesize():
    """Tổng hợp giọng nói"""
    data = request.get_json()
    
    if not data.get('text'):
        return jsonify({'error': 'Vui lòng nhập văn bản'}), 400
    
    text = data['text']
    voice_type = data.get('voice_type', 'edge_tts')
    voice_id = data.get('voice_id')
    speed = float(data.get('speed', 1.0))
    pitch = float(data.get('pitch', 0.0))
    
    # Generate output filename
    output_id = str(uuid.uuid4())
    output_file = os.path.join(Config.OUTPUT_FOLDER, f"{output_id}.mp3")
    
    try:
        success = False
        
        if voice_type == 'edge_tts':
            # Use Edge TTS
            voice_id = voice_id or 'vi-VN-HoaiMyNeural'
            
            # Calculate rate and pitch
            rate = f"{int((speed - 1) * 100):+d}%"
            pitch_hz = f"{int(pitch):+d}Hz"
            
            # Run async
            async def edge_synthesize():
                communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch_hz)
                await communicate.save(output_file)
            
            asyncio.run(edge_synthesize())
            success = True
            
        elif voice_type == 'cloned':
            # Use cloned voice
            if not voice_id:
                return jsonify({'error': 'Vui lòng chọn voice profile'}), 400
            
            profile_id = int(voice_id)
            profile = VoiceProfile.query.get(profile_id)
            
            if not profile:
                return jsonify({'error': 'Voice profile không tồn tại'}), 404
            
            # Check ownership or public
            if profile.user_id != request.current_user.id and not profile.is_public:
                return jsonify({'error': 'Không có quyền sử dụng voice này'}), 403
            
            success, result = voice_cloner.synthesize(text, profile_id, output_file)
            
            if not success:
                return jsonify({'error': result}), 500
        
        else:
            return jsonify({'error': 'Voice type không hỗ trợ'}), 400
        
        if success and os.path.exists(output_file):
            # Get file info
            file_size = os.path.getsize(output_file)
            
            # Get duration
            duration = 0
            try:
                audio_data, sample_rate = librosa.load(output_file, sr=None)
                duration = len(audio_data) / sample_rate
            except:
                pass
            
            # Save to history
            history = TTSHistory(
                user_id=request.current_user.id,
                text=text,
                voice_type=voice_type,
                voice_id=voice_id,
                output_file_path=output_file,
                file_size=file_size,
                duration=duration,
                speed=speed,
                pitch=pitch,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            if voice_type == 'cloned':
                history.voice_profile_id = profile_id
            
            db.session.add(history)
            db.session.commit()
            
            # Return download URL
            download_url = f"/api/tts/download/{output_id}"
            
            return jsonify({
                'message': 'Tổng hợp thành công',
                'download_url': download_url,
                'file_size': file_size,
                'duration': duration
            }), 200
        
        else:
            return jsonify({'error': 'Tổng hợp thất bại'}), 500
            
    except Exception as e:
        print(f"Error in synthesis: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tts/download/<output_id>')
def download_tts(output_id):
    """Download TTS output"""
    # Validate output_id (UUID format)
    try:
        uuid.UUID(output_id)
    except ValueError:
        return jsonify({'error': 'Invalid output ID'}), 400
    
    filepath = os.path.join(Config.OUTPUT_FOLDER, f"{output_id}.mp3")
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File không tồn tại'}), 404
    
    return send_file(filepath, as_attachment=True, download_name=f"tts_vietnamese_{output_id}.mp3")

@app.route('/api/tts/history', methods=['GET'])
@jwt_required
def get_tts_history():
    """Lấy lịch sử TTS của user"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    history = request.current_user.tts_history.order_by(
        TTSHistory.created_at.desc()
    ).paginate(page=page, per_page=per_page)
    
    return jsonify({
        'history': [h.to_dict() for h in history.items],
        'total': history.total,
        'pages': history.pages,
        'current_page': page
    }), 200

# Routes - Admin
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    """Admin: Lấy danh sách users"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    users = User.query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        'users': [u.to_dict() for u in users.items],
        'total': users.total,
        'pages': users.pages,
        'current_page': page
    }), 200

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def admin_update_user(user_id):
    """Admin: Cập nhật user"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    if 'role' in data and data['role'] in ['user', 'admin']:
        user.role = data['role']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Cập nhật thành công',
        'user': user.to_dict()
    }), 200

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """Admin: Thống kê hệ thống"""
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_voice_profiles': VoiceProfile.query.count(),
        'trained_profiles': VoiceProfile.query.filter_by(is_trained=True).count(),
        'total_tts_requests': TTSHistory.query.count(),
        'today_requests': TTSHistory.query.filter(
            TTSHistory.created_at >= datetime.utcnow().date()
        ).count()
    }
    
    return jsonify(stats), 200

# Routes - Public endpoints
@app.route('/api/voices', methods=['GET'])
def get_available_voices():
    """Lấy danh sách giọng có sẵn"""
    voices = {
        'edge_tts': [
            {'id': 'vi-VN-HoaiMyNeural', 'name': 'HoaiMy (Nữ)', 'language': 'vi-VN'},
            {'id': 'vi-VN-NamMinhNeural', 'name': 'NamMinh (Nam)', 'language': 'vi-VN'}
        ],
        'public_cloned': []
    }
    
    # Add public cloned voices
    public_profiles = VoiceProfile.query.filter_by(
        is_public=True,
        is_active=True,
        is_trained=True
    ).all()
    
    for profile in public_profiles:
        voices['public_cloned'].append({
            'id': str(profile.id),
            'name': profile.profile_name,
            'description': profile.description,
            'usage_count': profile.usage_count
        })
    
    return jsonify(voices), 200

# DEMO endpoint (không cần login)
@app.route('/api/demo/synthesize', methods=['POST'])
def demo_synthesize():
    """Demo TTS không cần đăng nhập"""
    data = request.get_json()
    
    if not data.get('text'):
        return jsonify({'error': 'Vui lòng nhập văn bản'}), 400
    
    text = data['text']
    # Giới hạn 200 ký tự cho demo
    if len(text) > 200:
        return jsonify({'error': 'Demo giới hạn 200 ký tự'}), 400
    
    voice_id = data.get('voice_id', 'vi-VN-HoaiMyNeural')
    speed = float(data.get('speed', 1.0))
    pitch = float(data.get('pitch', 0.0))
    
    # Generate output
    output_id = str(uuid.uuid4())
    output_file = os.path.join(Config.OUTPUT_FOLDER, f"demo_{output_id}.mp3")
    
    try:
        # Calculate rate and pitch
        rate = f"{int((speed - 1) * 100):+d}%"
        pitch_hz = f"{int(pitch):+d}Hz"
        
        # Run async
        async def edge_synthesize():
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch_hz)
            await communicate.save(output_file)
        
        asyncio.run(edge_synthesize())
        
        # Return audio URL
        return jsonify({
            'audio_url': f"/api/tts/download/demo_{output_id}"
        }), 200
        
    except Exception as e:
        print(f"Demo error: {e}")
        return jsonify({'error': 'Lỗi tạo demo'}), 500

# Error handlers
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint không tồn tại'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Lỗi server'}), 500
    return render_template('500.html'), 500

# CLI commands
@app.cli.command()
def init_db():
    """Initialize database"""
    db.create_all()
    print("✅ Database initialized")

@app.cli.command()
def create_admin():
    """Create admin user"""
    import click
    
    username = click.prompt('Admin username')
    email = click.prompt('Admin email')
    password = click.prompt('Admin password', hide_input=True)
    
    admin = User(
        username=username,
        email=email,
        full_name='Administrator',
        role='admin'
    )
    admin.set_password(password)
    
    db.session.add(admin)
    db.session.commit()
    
    print(f"✅ Admin user '{username}' created")

if __name__ == '__main__':
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Run app
    app.run(debug=True, host='0.0.0.0', port=5000)