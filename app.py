from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/uploads"


app = Flask(__name__)
app.secret_key = "supersecretkey"

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'lnetwork'
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

mysql = MySQL(app)


@app.route("/")
def home():
    return render_template("feed.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",
                    (username, password))
        user = cur.fetchone()

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cur = mysql.connection.cursor()

        # Проверяем существует ли пользователь
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            return "Пользователь уже существует!"

        # Добавляем нового пользователя
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, password)
        )
        mysql.connection.commit()

        return redirect("/login")

    return render_template("register.html")

@app.route("/profile")
def my_profile():
    if "user_id" not in session:
        return redirect("/login")
    return redirect(f"/profile/{session['user_id']}")

@app.route("/profile/<int:user_id>")
def profile_view(user_id):
    cur = mysql.connection.cursor()

    # Данные пользователя
    cur.execute("SELECT id, username, avatar FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    if not user:
        return "Пользователь не найден", 404

    # Посты
    cur.execute("SELECT posts.id, posts.content, posts.created_at FROM posts WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
    posts = cur.fetchall()

    own_profile = ("user_id" in session and session["user_id"] == user_id)

    # Количество друзей (включаем и тех, кто добавил пользователя)
    cur.execute("""
        SELECT COUNT(*) FROM friends 
        WHERE user_id=%s OR friend_id=%s
    """, (user_id, user_id))
    friend_count = cur.fetchone()[0]

    # Проверка, друзья ли текущий пользователь
    is_friend = False
    if "user_id" in session and not own_profile:
        cur.execute("SELECT * FROM friends WHERE user_id=%s AND friend_id=%s", (session["user_id"], user_id))
        is_friend = bool(cur.fetchone())

    return render_template("profile.html", user=user, posts=posts, own_profile=own_profile, friend_count=friend_count, is_friend=is_friend)


@app.route("/news")
def news():
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    # Берём посты + имя автора + id пользователя + количество лайков
    cur.execute("""
        SELECT posts.id, posts.content, posts.created_at, users.username, users.id as user_id,
        (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) as like_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    """)
    posts = cur.fetchall()

    return render_template("news.html", posts=posts)




@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    if "user_id" not in session:
        return redirect("/login")

    if "avatar" not in request.files:
        return redirect("/profile")

    file = request.files["avatar"]

    if file.filename == "":
        return redirect("/profile")

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE users SET avatar = %s WHERE id = %s",
        (filename, session["user_id"])
    )
    mysql.connection.commit()

    return redirect("/profile")


@app.route("/create_post", methods=["POST"])
def create_post():
    if "user_id" not in session:
        return redirect("/login")

    content = request.form["content"]

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO posts (user_id, content) VALUES (%s, %s)",
        (session["user_id"], content)
    )
    mysql.connection.commit()
    return redirect("/news")

@app.route("/like/<int:post_id>")
def like(post_id):
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    # Проверяем, лайкнул ли уже пользователь
    cur.execute(
        "SELECT * FROM likes WHERE post_id=%s AND user_id=%s",
        (post_id, session["user_id"])
    )
    existing = cur.fetchone()

    if not existing:
        cur.execute(
            "INSERT INTO likes (post_id, user_id) VALUES (%s, %s)",
            (post_id, session["user_id"])
        )
        mysql.connection.commit()

    return redirect("/news")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# Добавить в друзья
@app.route("/add_friend/<int:friend_id>")
def add_friend(friend_id):
    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]

    if current_user == friend_id:
        return redirect(f"/profile/{friend_id}")

    cur = mysql.connection.cursor()

    # Проверяем есть ли уже
    cur.execute("SELECT * FROM friends WHERE user_id=%s AND friend_id=%s", (current_user, friend_id))
    existing = cur.fetchone()

    if not existing:
        cur.execute("INSERT INTO friends (user_id, friend_id) VALUES (%s, %s)", (current_user, friend_id))
        mysql.connection.commit()

    return redirect(f"/profile/{friend_id}")


# Удалить из друзей
@app.route("/remove_friend/<int:friend_id>")
def remove_friend(friend_id):
    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]
    cur = mysql.connection.cursor()

    cur.execute("DELETE FROM friends WHERE user_id=%s AND friend_id=%s", (current_user, friend_id))
    mysql.connection.commit()

    return redirect(f"/profile/{friend_id}")


@app.route("/friends")
def friends():
    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]
    cur = mysql.connection.cursor()

    # Мои друзья (я добавил)
    cur.execute("""
        SELECT u.id, u.username, u.avatar
        FROM users u
        JOIN friends f ON f.friend_id = u.id
        WHERE f.user_id = %s
    """, (current_user,))
    my_friends = cur.fetchall()

    # Друзья, которые добавили меня, но я их не добавил
    cur.execute("""
        SELECT u.id, u.username, u.avatar
        FROM users u
        JOIN friends f ON f.user_id = u.id
        WHERE f.friend_id = %s
          AND u.id NOT IN (SELECT friend_id FROM friends WHERE user_id = %s)
    """, (current_user, current_user))
    added_me = cur.fetchall()

    return render_template("friends.html", my_friends=my_friends, added_me=added_me)




@app.route("/channels")
def channels():
    cur = mysql.connection.cursor()
    user_id = session.get("user_id")
    search_query = request.args.get("q", "").strip()

    # Поиск по названию
    sql = "SELECT id, name, description, creator_id, avatar FROM channels"
    params = []
    if search_query:
        sql += " WHERE name LIKE %s"
        params.append(f"%{search_query}%")
    sql += " ORDER BY id DESC"

    cur.execute(sql, tuple(params))
    channels = cur.fetchall()

    channels_list = []
    for ch in channels:
        # Количество подписчиков
        cur.execute("SELECT COUNT(*) FROM channel_subscriptions WHERE channel_id=%s", (ch[0],))
        subscribers_count = cur.fetchone()[0]

        # Проверка подписки пользователя
        is_subscribed = False
        if user_id:
            cur.execute(
                "SELECT 1 FROM channel_subscriptions WHERE channel_id=%s AND user_id=%s",
                (ch[0], user_id)
            )
            if cur.fetchone():
                is_subscribed = True

        # Добавляем в список каналов с дополнительными данными
        channels_list.append((*ch, subscribers_count, is_subscribed))

    return render_template("channels.html",
                           channels_list=channels_list,
                           user_id=user_id,
                           search_query=search_query)


@app.route("/channels/create", methods=["GET", "POST"])
def create_channel():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO channels (name, description, creator_id) VALUES (%s,%s,%s)",
                    (name, description, session["user_id"]))
        mysql.connection.commit()
        return redirect("/channels")

    return render_template("create_channel.html")


# Просмотр канала
@app.route("/channel/<int:channel_id>")
def channel_view(channel_id):
    cur = mysql.connection.cursor()

    # Данные канала
    cur.execute("SELECT id, name, description, creator_id FROM channels WHERE id=%s", (channel_id,))
    channel = cur.fetchone()
    if not channel:
        return "Канал не найден", 404

    # Проверяем подписку (только если это не админ)
    is_subscribed = False
    if "user_id" in session and session["user_id"] != channel[3]:
        cur.execute("SELECT * FROM channel_subscriptions WHERE channel_id=%s AND user_id=%s",
                    (channel_id, session["user_id"]))
        if cur.fetchone():
            is_subscribed = True

    # Количество подписчиков канала
    cur.execute("SELECT COUNT(*) FROM channel_subscriptions WHERE channel_id=%s", (channel_id,))
    subscribers_count = cur.fetchone()[0]

    cur.execute("SELECT id, name, description, creator_id, avatar FROM channels WHERE id=%s", (channel_id,))
    channel = cur.fetchone()

    # Посты канала + имя и аватар автора + количество лайков
    cur.execute("""
        SELECT cp.id, cp.content, cp.created_at, u.username, u.avatar,
        (SELECT COUNT(*) FROM channel_post_likes WHERE post_id=cp.id) AS like_count
        FROM channel_posts cp
        JOIN users u ON cp.user_id = u.id
        WHERE cp.channel_id=%s
        ORDER BY cp.created_at DESC
    """, (channel_id,))
    posts = cur.fetchall()

    return render_template(
        "channel_view.html",
        channel=channel,
        is_subscribed=is_subscribed,
        subscribers_count=subscribers_count,
        posts=posts
    )



# Подписаться
@app.route("/subscribe/<int:channel_id>")
def subscribe(channel_id):
    if "user_id" not in session:
        return redirect("/login")
    cur = mysql.connection.cursor()
    cur.execute("INSERT IGNORE INTO channel_subscriptions (channel_id, user_id) VALUES (%s,%s)",
                (channel_id, session["user_id"]))
    mysql.connection.commit()
    return redirect(f"/channel/{channel_id}")


# Отписаться
@app.route("/unsubscribe/<int:channel_id>")
def unsubscribe(channel_id):
    if "user_id" not in session:
        return redirect("/login")
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM channel_subscriptions WHERE channel_id=%s AND user_id=%s",
                (channel_id, session["user_id"]))
    mysql.connection.commit()
    return redirect(f"/channel/{channel_id}")


# Создать пост в канале
@app.route("/channel/<int:channel_id>/post", methods=["POST"])
def channel_post(channel_id):
    if "user_id" not in session:
        return redirect("/login")
    cur = mysql.connection.cursor()
    # Проверка, что админ
    cur.execute("SELECT creator_id FROM channels WHERE id=%s", (channel_id,))
    creator = cur.fetchone()
    if not creator or creator[0] != session["user_id"]:
        return "Нет прав", 403

    content = request.form["content"]
    cur.execute("INSERT INTO channel_posts (channel_id, user_id, content) VALUES (%s,%s,%s)",
                (channel_id, session["user_id"], content))
    mysql.connection.commit()
    return redirect(f"/channel/{channel_id}")


# Лайк поста канала
@app.route("/channel/post/like/<int:post_id>")
def like_channel_post(post_id):
    if "user_id" not in session:
        return redirect("/login")
    cur = mysql.connection.cursor()
    cur.execute("INSERT IGNORE INTO channel_post_likes (post_id, user_id) VALUES (%s,%s)",
                (post_id, session["user_id"]))
    mysql.connection.commit()
    # Определяем канал поста, чтобы вернуться
    cur.execute("SELECT channel_id FROM channel_posts WHERE id=%s", (post_id,))
    channel_id = cur.fetchone()[0]
    return redirect(f"/channel/{channel_id}")

# Страница настроек канала (только админ)
@app.route("/channel/<int:channel_id>/settings", methods=["GET", "POST"])
def channel_settings(channel_id):
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()
    user_id = session["user_id"]

    # Получаем канал
    cur.execute("SELECT id, name, description, creator_id, avatar FROM channels WHERE id=%s", (channel_id,))
    channel = cur.fetchone()
    if not channel:
        return "Канал не найден", 404

    # Проверяем, что это админ
    if channel[3] != user_id:
        return "Нет доступа", 403

    if request.method == "POST":
        # Обновляем название и описание
        name = request.form.get("name").strip()
        description = request.form.get("description").strip()

        # Проверяем файл аватара
        avatar_file = request.files.get("avatar")
        avatar_filename = channel[4]  # по умолчанию текущий

        if avatar_file and avatar_file.filename != "":
            from werkzeug.utils import secure_filename
            import os
            avatar_filename = secure_filename(avatar_file.filename)
            avatar_path = os.path.join("static/uploads", avatar_filename)
            avatar_file.save(avatar_path)

        # Сохраняем изменения
        cur.execute("""
            UPDATE channels SET name=%s, description=%s, avatar=%s WHERE id=%s
        """, (name, description, avatar_filename, channel_id))
        mysql.connection.commit()

        return redirect(f"/channel/{channel_id}")

    return render_template("channel_settings.html", channel=channel)


if __name__ == "__main__":
    app.run(debug=True)
