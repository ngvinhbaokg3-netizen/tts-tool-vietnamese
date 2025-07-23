import os
import shutil
import sys

def create_directory_structure():
    """Tạo cấu trúc thư mục"""
    directories = [
        'templates',
        'static',
        'static/css',
        'static/js',
        'static/img',
        'uploads',
        'outputs',
        'voice_samples',
        'logs'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created {directory}")
        
        # Create .gitkeep for empty directories
        if directory in ['uploads', 'outputs', 'voice_samples', 'logs']:
            gitkeep_path = os.path.join(directory, '.gitkeep')
            open(gitkeep_path, 'a').close()

def create_env_file():
    """Tạo file .env từ .env.example"""
    if not os.path.exists('.env') and os.path.exists('.env.example'):
        shutil.copy('.env.example', '.env')
        print("✓ Created .env file from .env.example")
        print("⚠️  Please update .env with your settings!")

def check_requirements():
    """Kiểm tra Python version"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required!")
        sys.exit(1)
    print(f"✓ Python {sys.version}")

def main():
    print("🚀 TTS Tool Vietnamese - Setup Script")
    print("=" * 50)
    
    # Check requirements
    check_requirements()
    
    # Create directories
    print("\n📁 Creating directory structure...")
    create_directory_structure()
    
    # Create env file
    print("\n🔧 Setting up configuration...")
    create_env_file()
    
    print("\n✅ Setup completed!")
    print("\n📝 Next steps:")
    print("1. Update .env file with your configuration")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Initialize database: flask db upgrade")
    print("4. Create admin user: flask create-admin")
    print("5. Run application: python app.py")
    
    print("\n💡 For production deployment:")
    print("   docker-compose up -d")

if __name__ == "__main__":
    main()