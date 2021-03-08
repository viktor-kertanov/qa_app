from flask import Flask, render_template, g, request, session, redirect, url_for
from database import get_db
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


def get_current_user():
    user_result = None
    if 'user' in session:
        user = session['user']
        db = get_db()
        user_cur = db.execute('select id, name, password, expert, admin from users where name = ?', [user])
        user_result = user_cur.fetchone()
    return user_result

@app.route('/')
def index():
    user = get_current_user()
    db = get_db()
    answered_cur = db.execute("""
    select
        questions.id,
        questions.question_text,
        askers.name as asker,
        experts.name as expert
    from
        questions
    left join users as askers on
    askers.id = questions.asked_by_id
    left join users as experts on
    experts.id = questions.expert_id  
    where answer_text is not null""")
    answered = answered_cur.fetchall()
    return render_template('home.html', user=user, answered=answered)

@app.route('/register', methods=['POST', 'GET'])
def register():
    user = get_current_user()
    if request.method == "POST":
        db = get_db()
        existing_user_cur = db.execute('select id from users where name = ?',[request.form['name']])
        existing_user = existing_user_cur.fetchone()
        if existing_user:
            return render_template('register.html', user=user, error="User already exists!")


        hashed_password = generate_password_hash(request.form['password'], method='sha256')
        db.execute('insert into users (name, password, expert, admin) values(?,?,?,?)',
                   [request.form['name'], hashed_password, '0', '0']
                   )
        db.commit()
        session['user'] = request.form['name']

        # return f"<h1>User created! Password: {hashed_password}</h1>"
        return redirect(url_for('index'))
    return render_template('register.html', user=user)

@app.route('/login', methods=["GET", "POST"])
def login():
    user = get_current_user()
    error = None
    if request.method == "POST":
        db = get_db()

        name = request.form['name']
        password = request.form['password']

        user_cur = db.execute("""select id, name, password from users where name = ?""",[name])
        user_result = user_cur.fetchone()

        if user_result:
            if check_password_hash(user_result["password"], password):
                session['user'] = user_result['name']
                # return f"<h1>The password is correct for {user_result['name']}"
                return (redirect(url_for('index')))
            else:
                error = "The password is incorrect!"
                # return f"<h1>The password is incorrect!</h1>"
        else:
            error = "The username is incorrect!"
        # return '<h1>The username is incorrect!</h1>'
    return render_template('login.html', user=user, error=error)

@app.route('/question/<question_id>')
def question(question_id):
    user = get_current_user()
    db = get_db()
    qa_cur = db.execute("""
    select
    questions.id,
    questions.question_text,
    questions.answer_text,
    askers.name as asker,
    experts.name as expert
    from
    questions
    left join users as askers on
    askers.id = questions.asked_by_id
    left join users as experts on
    experts.id = questions.expert_id
    where
    questions.id = ?
    """, [question_id])
    qa = qa_cur.fetchone()

    return render_template('question.html', user=user, qa=qa)

@app.route('/answer/<question_id>', methods=["GET","POST"])
def answer(question_id):
    user = get_current_user()

    if not user:
        return redirect(url_for('login'))
    if user['expert'] == 0:
        return redirect(url_for('index'))

    db = get_db()
    if request.method == "POST":
        # return f"<h1>Question id: {question_id}. Answer: {request.form['answer']}</h1>"
        db.execute('update questions set answer_text = ? where id = ?', [request.form['answer'], question_id])
        db.commit()
        return redirect(url_for('unanswered'))
    question_cur = db.execute('select id, question_text from questions where id = ?', [question_id])
    question = question_cur.fetchone()
    return render_template('answer.html', user=user, question=question)

@app.route('/ask', methods=['GET', 'POST'])
def ask ():
    user = get_current_user()

    if not user:
        return redirect(url_for('login'))

    db = get_db()
    if request.method == "POST":
        db.execute('insert into questions (question_text, asked_by_id, expert_id) values (?,?,?)',
                   [request.form['question'], user['id'], request.form['expert']])
        db.commit()
        # return f"<h1>Question: {request.form['question']}, Expert ID: {request.form['expert']}</h1>"
        return redirect(url_for('index'))
    expert_cur = db.execute("select id, name from users where expert = 1")
    experts = expert_cur.fetchall()
    return render_template('ask.html', user=user, experts=experts)

@app.route('/unanswered', methods=['GET', 'POST'])
def unanswered():
    user = get_current_user()

    if not user:
        return redirect(url_for('login'))
    if user['expert'] == 0:
        return redirect(url_for('index'))

    db = get_db()
    questions_cur = db.execute("""
    select
        questions.id as id,
        questions.question_text as questions,
        users.name as name
    from questions
    join users on 
        users.id = questions.asked_by_id
    where 
     questions.answer_text is null and
     questions.expert_id = ?""", [user['id']])
    questions = questions_cur.fetchall()
    return render_template('unanswered.html', user=user, questions=questions)

@app.route('/users')
def users():
    user = get_current_user()

    if not user:
        return redirect(url_for('login'))
    if user['admin'] == 0:
        return redirect(url_for('index'))

    db = get_db()
    users_cur = db.execute('select id, name, expert, admin from users')
    users = users_cur.fetchall()
    return render_template('users.html', user=user, users=users)


@app.route('/promote/<user_id>')
def promote(user_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['admin'] == 0:
        return redirect(url_for('index'))
    db = get_db()
    expert_status_cur = db.execute('select expert from users where id = ?', [user_id])
    expert_status = expert_status_cur.fetchone()
    if expert_status['expert'] == 1:
        db.execute('update users set expert = 0 where id = ?', [user_id])
        db.commit()
    else:
        db.execute('update users set expert = 1 where id = ?', [user_id])
        db.commit()
    return redirect(url_for('users'))


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


if __name__ == '__main__)':
    app.run(Debug=True)
