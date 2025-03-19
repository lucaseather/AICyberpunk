from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from translate import Translator
from gtts import gTTS
import os
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import tempfile
import json
import logging
from logging.handlers import RotatingFileHandler
import click
import sqlite3
from flask import g

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dictionary.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'  # 請更改为安全的密钥

# 設置日誌
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('應用程序啟動')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    collections = db.relationship('Collection', backref='user', lazy=True)
    study_records = db.relationship('StudyRecord', backref='user', lazy=True)
    search_history = db.relationship('SearchHistory', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 单词模型
class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    translation = db.Column(db.String(500), nullable=False)
    examples = db.relationship('Example', backref='word', lazy=True)
    category = db.Column(db.String(50))
    difficulty = db.Column(db.Integer)  # 1-5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 例句模型
class Example(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    english = db.Column(db.String(500), nullable=False)
    chinese = db.Column(db.String(500), nullable=False)
    audio_url = db.Column(db.String(200))

# 收藏夹模型
class Collection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    words = db.relationship('Word', secondary='collection_words')

# 收藏夹-单词关联表
collection_words = db.Table('collection_words',
    db.Column('collection_id', db.Integer, db.ForeignKey('collection.id'), primary_key=True),
    db.Column('word_id', db.Integer, db.ForeignKey('word.id'), primary_key=True)
)

# 学习记录模型
class StudyRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    status = db.Column(db.String(20))  # 'new', 'learning', 'reviewed'
    next_review = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 搜索历史模型
class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    translation = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 创建数据库表
with app.app_context():
    try:
        print("開始創建數據庫表...")
        db.drop_all()  # 删除所有表
        print("已刪除所有表")
        db.create_all()  # 重新创建所有表
        print("數據庫表創建成功！")
    except Exception as e:
        print(f"數據庫表創建失敗：{str(e)}")
        raise e

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    word = request.form.get('word', '')
    if not word:
        return jsonify({'error': '請輸入要查詢的單字'})

    try:
        # 檢測語言並翻譯
        if any(ord(c) > 127 for c in word):  # 如果包含中文字符
            translator = Translator(to_lang='en', from_lang='zh')
        else:
            translator = Translator(to_lang='zh', from_lang='en')
        
        translation = translator.translate(word)

        # 生成例句
        if any(ord(c) > 127 for c in word):  # 如果包含中文字符
            # 中文到英文的例句
            example_english = f"I want to learn how to use '{word}' in English."
            example_chinese = f"我想學習如何在英語中使用'{word}'。"
        else:
            # 英文到中文的例句
            if word.lower() in ['hello', 'hi', 'goodbye', 'bye']:
                example_english = f"{word.capitalize()}, how are you today?"
                example_chinese = f"{word.capitalize()}，今天過得怎麼樣？"
            elif word.lower() in ['thank', 'thanks', 'thank you']:
                example_english = f"{word.capitalize()} for your help!"
                example_chinese = f"感謝你的幫助！"
            elif word.lower() in ['sorry', 'apologize']:
                example_english = f"I'm {word} for being late."
                example_chinese = f"抱歉我遲到了。"
            else:
                example_english = f"I need to look up the meaning of '{word}' in the dictionary."
                example_chinese = f"我需要在字典中查找'{word}'的含義。"

        examples = [
            {
                "english": example_english,
                "chinese": example_chinese
            }
        ]

        # 保存到歷史記錄
        if current_user.is_authenticated:
            history = SearchHistory(word=word, translation=translation, user_id=current_user.id)
        else:
            history = SearchHistory(word=word, translation=translation)
        db.session.add(history)
        db.session.commit()

        # 生成語音文件
        tts = gTTS(text=word, lang='en')
        audio_path = os.path.join('static', 'audio', f'{word}.mp3')
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        tts.save(audio_path)

        return jsonify({
            'word': word,
            'translation': translation,
            'audio_url': f'/static/audio/{word}.mp3',
            'examples': examples
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/history')
@login_required
def get_history():
    history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).limit(10).all()
    return jsonify([{
        'word': h.word,
        'translation': h.translation,
        'timestamp': h.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for h in history])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        user = User.query.filter_by(email=data.get('email')).first()
        if user and user.check_password(data.get('password')):
            login_user(user)
            return jsonify({'success': True})
        return jsonify({'error': '郵箱或密碼錯誤'})
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({'error': '該郵箱已被註冊'})
        if User.query.filter_by(username=data.get('username')).first():
            return jsonify({'error': '該用戶名已被使用'})
        
        user = User(
            username=data.get('username'),
            email=data.get('email')
        )
        user.set_password(data.get('password'))
        db.session.add(user)
        db.session.commit()
        return jsonify({'success': True})
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/collections', methods=['GET', 'POST'])
@login_required
def collections():
    return render_template('collections.html')

@app.route('/api/collections', methods=['GET', 'POST'])
@login_required
def handle_collections():
    if request.method == 'GET':
        # 獲取用戶的收藏列表
        try:
            # 使用 SQLAlchemy 查詢
            collections = Collection.query.filter_by(
                name="我的收藏",
                user_id=current_user.id
            ).first()
            
            if not collections:
                return jsonify([])
            
            words = [{
                'word': word.word,
                'translation': word.translation
            } for word in collections.words]
            
            return jsonify(words)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        # 添加單字到收藏夾
        data = request.get_json()
        if not data or 'word' not in data or 'translation' not in data:
            return jsonify({'error': '缺少必要參數'}), 400

        word_text = data['word']
        translation = data['translation']

        try:
            # 獲取或創建默認收藏夾
            collection = Collection.query.filter_by(
                name="我的收藏",
                user_id=current_user.id
            ).first()
            
            if not collection:
                collection = Collection(
                    name="我的收藏",
                    user_id=current_user.id
                )
                db.session.add(collection)
                db.session.commit()
            
            # 檢查單字是否已存在
            word = Word.query.filter_by(word=word_text).first()
            if not word:
                word = Word(
                    word=word_text,
                    translation=translation
                )
                db.session.add(word)
                db.session.commit()
            
            # 將單字加入收藏夾
            if word not in collection.words:
                collection.words.append(word)
                db.session.commit()
                return jsonify({'success': True})
            else:
                return jsonify({'error': '該單字已在收藏夾中'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@app.route('/api/collections/<string:word>', methods=['DELETE'])
@login_required
def remove_from_collection(word):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'DELETE FROM collections WHERE user_id = ? AND word = ?',
            (g.user['id'], word)
        )
        db.commit()
        return jsonify({'message': '移除成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/collections/<int:collection_id>/words', methods=['GET', 'POST'])
@login_required
def collection_words(collection_id):
    try:
        print(f"處理收藏夾 {collection_id} 的請求...")
        collection = Collection.query.get_or_404(collection_id)
        if collection.user_id != current_user.id:
            print("無權訪問該收藏夾")
            return jsonify({'error': '無權訪問'}), 403
        
        if request.method == 'POST':
            data = request.get_json()
            print(f"接收到的數據：{data}")
            word_text = data.get('word')
            translation = data.get('translation')
            
            # 檢查單字是否已存在
            word = Word.query.filter_by(word=word_text).first()
            if not word:
                print(f"創建新單字：{word_text}")
                word = Word(
                    word=word_text,
                    translation=translation
                )
                db.session.add(word)
                db.session.commit()
            
            # 將單字加入收藏夾
            if word not in collection.words:
                print(f"將單字 {word_text} 加入收藏夾")
                collection.words.append(word)
                db.session.commit()
                return jsonify({'success': True})
            else:
                print(f"單字 {word_text} 已在收藏夾中")
                return jsonify({'error': '該單字已在收藏夾中'})
        
        print(f"獲取收藏夾 {collection_id} 的單字列表")
        return jsonify([{
            'id': w.id,
            'word': w.word,
            'translation': w.translation
        } for w in collection.words])
    except Exception as e:
        print(f"處理收藏夾請求失敗：{str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/study/next', methods=['GET'])
@login_required
def get_next_word():
    # 獲取需要複習的單字
    next_review = StudyRecord.query.filter_by(
        user_id=current_user.id,
        status='learning'
    ).filter(StudyRecord.next_review <= datetime.utcnow()).first()
    
    if not next_review:
        return jsonify({'error': '沒有需要複習的單字'})
    
    word = Word.query.get(next_review.word_id)
    return jsonify({
        'id': word.id,
        'word': word.word,
        'translation': word.translation
    })

@app.route('/study/list')
def study_list_page():
    return render_template('study_list.html')

@app.route('/study/statistics')
def statistics_page():
    return render_template('statistics.html')

@app.route('/study/test')
def test_page():
    return render_template('test.html')

@app.route('/collections')
@login_required
def collections_page():
    return render_template('collections.html')

@app.route('/api/user/status')
def user_status():
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'username': current_user.username
        })
    return jsonify({
        'authenticated': False,
        'username': None
    })

@app.route('/api/collections', methods=['GET', 'POST'])
@login_required
def api_collections():
    if request.method == 'POST':
        try:
            data = request.get_json()
            word_text = data.get('word')
            translation = data.get('translation')
            
            if not word_text or not translation:
                return jsonify({'error': '缺少必要參數'})
            
            # 獲取或創建默認收藏夾
            collection = Collection.query.filter_by(
                name="我的收藏",
                user_id=current_user.id
            ).first()
            
            if not collection:
                collection = Collection(
                    name="我的收藏",
                    user_id=current_user.id
                )
                db.session.add(collection)
                db.session.commit()
            
            # 檢查單字是否已存在
            word = Word.query.filter_by(word=word_text).first()
            if not word:
                word = Word(
                    word=word_text,
                    translation=translation
                )
                db.session.add(word)
                db.session.commit()
            
            # 將單字加入收藏夾
            if word not in collection.words:
                collection.words.append(word)
                db.session.commit()
                return jsonify({'success': True})
            else:
                return jsonify({'error': '該單字已在收藏夾中'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    else:
        try:
            collections = Collection.query.filter_by(user_id=current_user.id).all()
            return jsonify([{
                'id': c.id,
                'name': c.name,
                'word_count': len(c.words)
            } for c in collections])
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/collections/<int:collection_id>/words', methods=['GET'])
@login_required
def get_collection_words(collection_id):
    try:
        collection = Collection.query.filter_by(
            id=collection_id,
            user_id=current_user.id
        ).first()
        
        if not collection:
            return jsonify({'error': '找不到該收藏夾'}), 404
        
        words = [{
            'word': word.word,
            'translation': word.translation
        } for word in collection.words]
        
        return jsonify(words)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/collections/<int:collection_id>/words/<string:word>', methods=['DELETE'])
@login_required
def remove_word_from_collection(collection_id, word):
    try:
        collection = Collection.query.filter_by(
            id=collection_id,
            user_id=current_user.id
        ).first()
        
        if not collection:
            return jsonify({'error': '找不到該收藏夾'}), 404
        
        word_obj = Word.query.filter_by(word=word).first()
        if not word_obj:
            return jsonify({'error': '找不到該單字'}), 404
        
        if word_obj in collection.words:
            collection.words.remove(word_obj)
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': '該單字不在收藏夾中'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/study/list', methods=['GET', 'POST'])
@login_required
def api_study_list():
    if request.method == 'POST':
        try:
            data = request.get_json()
            word_text = data.get('word')
            translation = data.get('translation')
            
            if not word_text or not translation:
                return jsonify({'error': '缺少單字或翻譯'})
            
            # 檢查單字是否已存在
            word = Word.query.filter_by(word=word_text).first()
            if not word:
                word = Word(
                    word=word_text,
                    translation=translation
                )
                db.session.add(word)
                db.session.commit()
            
            # 檢查是否已在學習列表中
            record = StudyRecord.query.filter_by(
                user_id=current_user.id,
                word_id=word.id
            ).first()
            
            if not record:
                record = StudyRecord(
                    user_id=current_user.id,
                    word_id=word.id,
                    status='new',
                    next_review=datetime.utcnow()
                )
                db.session.add(record)
                db.session.commit()
                return jsonify({'success': True})
            else:
                return jsonify({'error': '該單字已在學習列表中'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    else:
        try:
            study_list = StudyRecord.query.filter_by(user_id=current_user.id).all()
            result = []
            for record in study_list:
                word = Word.query.get(record.word_id)
                if word:
                    result.append({
                        'word': word.word,
                        'translation': word.translation,
                        'status': record.status,
                        'next_review': record.next_review.strftime('%Y-%m-%d %H:%M:%S') if record.next_review else None
                    })
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/study/statistics')
@login_required
def api_statistics():
    try:
        records = StudyRecord.query.filter_by(user_id=current_user.id).all()
        total_words = len(records)
        mastered_words = len([r for r in records if r.status == 'reviewed'])
        review_words = len([r for r in records if r.status == 'learning'])
        
        total_time = total_words * 5
        today_records = [r for r in records if r.created_at.date() == datetime.utcnow().date()]
        today_time = len(today_records) * 5
        
        return jsonify({
            'total_words': total_words,
            'mastered_words': mastered_words,
            'review_words': review_words,
            'total_time': total_time,
            'today_time': today_time
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/study/test')
@login_required
def api_test():
    try:
        # 獲取需要複習的單字
        records = StudyRecord.query.filter_by(
            user_id=current_user.id,
            status='learning'
        ).filter(StudyRecord.next_review <= datetime.utcnow()).all()
        
        if not records:
            return jsonify({'error': '沒有需要複習的單字'})
        
        # 隨機選擇一個單字
        import random
        record = random.choice(records)
        word = Word.query.get(record.word_id)
        
        # 生成選項
        all_words = Word.query.all()
        options = [word.translation]
        while len(options) < 4:
            random_word = random.choice(all_words)
            if random_word.translation not in options:
                options.append(random_word.translation)
        random.shuffle(options)
        
        return jsonify({
            'word': word.word,
            'options': options,
            'total_words': len(records),
            'current_index': 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            'instance/cyberpunk.db',
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """初始化數據庫。"""
    db = get_db()
    with app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))
    db.commit()

@click.command('init-db')
def init_db_command():
    """初始化數據庫。"""
    with app.app_context():
        init_db()
        click.echo('數據庫初始化完成。')

app.cli.add_command(init_db_command)

if __name__ == '__main__':
    app.run(debug=True) 