from enum import unique

from flask import Flask,session, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import  SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@127.0.0.1:3306/library_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'library_secret_key_123'
db = SQLAlchemy(app)
# -------------------------- 数据库模型定义 --------------------------

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(50))
    isbn = db.Column(db.String(20), unique=True)
    status = db.Column(db.String(10), default='可借')
    borrow_time = db.Column(db.DateTime)
    return_time = db.Column(db.DateTime)
    borrower_id = db.Column(db.String(20))
class Reader(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reader_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(11))
    user_id = db.Column(db.Integer,db.ForeignKey('user.id') ,unique = True,  nullable=False)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='customer')
# -------------------------- 路由/功能定义 --------------------------
# 首页
@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html')
    return redirect(url_for('login_page'))
@app.route('/index_back')
def index_back():
    return render_template("index.html")
@app.route('/logout')
def logout():
    session.clear()
    flash("您已成功退出")
    return redirect(url_for('login_page'))

@app.route('/books', methods=['GET'])
def book_list():
    keyword = request.args.get('keyword', '').strip()

    if keyword:
        books = Book.query.filter(
            db.or_(Book.name.contains(keyword), Book.author.contains(keyword))
        ).all()
    else:
        books = Book.query.all()
    return render_template('books.html', books=books, keyword=keyword)
@app.route('/add_book', methods=['POST'])
def add_book():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    if session.get('role') != 'admin':
        flash('权限不足，只有管理员可以添加图书！')
        return redirect(url_for('book_list'))

    name = request.form.get('name').strip()
    author = request.form.get('author').strip()
    isbn = request.form.get('isbn').strip()

    if not name:
        flash('书名不能为空！')
        return redirect(url_for('book_list'))

    if Book.query.filter_by(isbn=isbn).first():
        flash(f'ISBN {isbn} 已存在！')
        return redirect(url_for('book_list'))

    new_book = Book(name=name, author=author, isbn=isbn)
    db.session.add(new_book)
    db.session.commit()
    flash('图书新增成功！')
    return redirect(url_for('book_list'))


@app.route('/add_reader', methods=['POST'])
def add_reader():
    if session.get('role') != 'admin':
        flash('权限不足，只有管理员可以添加读者！')
        return redirect(url_for('borrow_return_page'))

    r_id = request.form.get('reader_id', '').strip()
    r_name = request.form.get('name', '').strip()

    if not r_id or not r_name:
        flash('读者编号和姓名不能为空！')
        return redirect(url_for('borrow_return_page'))

    if Reader.query.filter_by(reader_id=r_id).first():
        flash(f'编号 {r_id} 已存在，请勿重复添加！')
        return redirect(url_for('borrow_return_page'))

    try:
        # 4. 核心逻辑：自动创建一个 User 账号（默认密码123456）
        new_user = User(username=r_name, password='123456', role='customer')
        db.session.add(new_user)
        db.session.flush()  # 刷入数据库以获取自动生成的 user_id
        new_reader = Reader(reader_id=r_id, name=r_name, user_id=new_user.id)
        db.session.add(new_reader)

        db.session.commit()
        flash(f'读者 {r_name} 添加成功！初始登录密码为 123456')
    except Exception as e:
        db.session.rollback()
        flash(f'添加失败，错误原因：{str(e)}')

    return redirect(url_for('borrow_return_page'))
@app.route('/borrow_return')
def borrow_return_page():
    if 'username' not in session:
        return redirect(url_for('login_page'))

    current_user_id = session.get('user_id')
    user_role = session.get('role') # 获取角色

    available_books = Book.query.filter_by(status='可借').all()

    if user_role == 'admin':
        readers = Reader.query.all()
        borrowed_books = Book.query.filter_by(status='已借').all()
    else:
        me = Reader.query.filter_by(user_id=current_user_id).first()
        readers = [me] if me else []
        if me:
            borrowed_books = Book.query.filter_by(status='已借', borrower_id=me.reader_id).all()
        else:
            borrowed_books = []

    # 修改点：将 role 传给模板
    return render_template('borrow_return.html',
                           available_books=available_books,
                           borrowed_books=borrowed_books,
                           readers=readers,
                           role=user_role)
@app.route('/borrow_book', methods=['POST'])
def borrow_book():
    book_id = request.form.get('book_id')
    reader_id = request.form.get('reader_id')

    book = Book.query.get(book_id)
    if book and book.status == '可借':
        book.status = '已借'
        book.borrow_time = datetime.now()
        book.borrower_id = reader_id
        db.session.commit()
        flash('借阅成功！')
    return redirect(url_for('borrow_return_page'))
@app.route('/return_book', methods=['POST'])
def return_book():
    book_id = request.form.get('book_id')
    book = Book.query.get(book_id)
    if not book:
        flash('图书不存在！')
        return redirect(url_for('borrow_return_page'))
    if book.status != '已借':
        flash(f'《{book.name}》当前未借出！')
        return redirect(url_for('borrow_return_page'))


    book.status = '可借'
    book.return_time = datetime.now()
    db.session.commit()

    flash(f'《{book.name}》归还成功！')
    return redirect(url_for('borrow_return_page'))
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        user_name = request.form.get('username').strip()
        pass_word = request.form.get('password').strip()
        user = User.query.filter_by(username=user_name , password = pass_word).first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            return redirect(url_for('index'))  # 登录成功，去首页
        else:
            return "账号或密码错误，请重新输入"
    return render_template('login.html')
# -------------------------- 初始化数据库 + 运行 --------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)