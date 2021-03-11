# ------------------ IMPORTS BLOCK ------------------

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy.orm import relationship
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
import datetime as dt
import json
from json.decoder import JSONDecodeError
from sqlalchemy.exc import OperationalError, IntegrityError
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_gravatar import Gravatar

# ------------------ END BLOCK ------------------


# ------------------ APPLICATION CONFIG BLOCK ------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)
months = [(i, dt.date(2008, i, 1).strftime('%B')) for i in range(1, 13)]

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)


# ------------------ END BLOCK ------------------

# ------------------ USER CONFIG ------------------

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    admin = db.Column(db.Boolean(), default=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")


# ------------------ DATABASE CONFIG ------------------

# ------ BLOG POSTS TABLE ------

class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(400), unique=True, nullable=False)
    subtitle = db.Column(db.String(400), nullable=False)
    date = db.Column(db.String(400), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(600), nullable=True)
    comments = relationship("Comment", back_populates="parent_post")


# ------ END ------


# ------ COMMENTS TABLE ------

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates='comments')
    comment = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(250), nullable=False)


# ------ END ------


# ------ DELETED POSTS TABLE ------

# class DeletedPost(db.Model):
#     __tablename__ = 'deleted_posts'
#     id = db.Column(db.Integer, primary_key=True)
#     author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
#     author = relationship("User", back_populates="comments")
#     post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
#     parent_post = relationship("BlogPost", back_populates='comments')
#     comment = db.Column(db.Text, nullable=False)
#     date = db.Column(db.String(250), nullable=False)


# ------ END ------

db.create_all()  # CREATE ALL TABLES


# ------------------ END ------------------


def get_posts():  # GET ALL EXISTING POSTS
    try:
        return BlogPost.query.all()
    except OperationalError:
        return []


def get_deleted():
    try:
        with open('deleted_posts.json', 'r') as data_file:
            return json.load(data_file)
    except FileNotFoundError:
        return []
    except JSONDecodeError:
        return []


def get_data():  # GET CONFIG DATA
    try:
        with open('data.json', 'r') as data_file:
            return json.load(data_file)
    except FileNotFoundError:
        return {}
    except JSONDecodeError:
        return {}


def check_errors():  # CHECK FOR ERRORS IN DATA
    errors = {}

    # ------ TEST 1, CHECK IF DATA FILE IS EMPTY ------

    try:
        with open('data.json', 'r') as data_file:
            test = json.load(data_file)
    except FileNotFoundError:
        errors["Data File"] = "Data File does not exist, no website configurations available."
    except JSONDecodeError:
        errors["Data File"] = "Data file is empty, no website configurations available."

    # ------ TEST END ------

    return errors


def get_name():
    data = get_data()
    if any(data):
        return data["website_configuration"]["name"]
    else:
        return "Website"


def get_background():
    try:
        return get_data()["website_configuration"]["background_image"]
    except KeyError:
        return "https://images.unsplash.com/photo-1470092306007-055b6797ca72?ixlib=rb-1.2.1&auto=format&fit=crop&w=668&q=80"


# ------------------ END BLOCK ------------------


# ------------------ FORMS ------------------


# ------ CREATE POST FORM ------

class CreatePostForm(FlaskForm):
    title = StringField("Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    img_url = StringField("Post Image URL")
    body = CKEditorField("Post Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ WEB CONFIGURATION FORM ------

class WebConfigForm(FlaskForm):
    name = StringField("Website Name", validators=[DataRequired()],
                       render_kw={"style": "margin-bottom: 10px;"})
    homepage_title = StringField("Homepage Title", validators=[DataRequired()],
                                 render_kw={"style": "margin-bottom: 10px;"})
    homepage_subtitle = StringField("Homepage Subtitle", validators=[DataRequired()],
                                    render_kw={"style": "margin-bottom: 10px;"})
    background_image = StringField("Background Image URL",
                                   render_kw={"style": "margin-bottom: 10px;"})
    twitter_link = StringField("Twitter Link", validators=[DataRequired(), URL()],
                               render_kw={"style": "margin-bottom: 10px;"})
    facebook_link = StringField("FaceBook Link", validators=[DataRequired(), URL()],
                                render_kw={"style": "margin-bottom: 10px;"})
    github_link = StringField("GitHub Link", validators=[DataRequired(), URL()],
                              render_kw={"style": "margin-bottom: 10px;"})
    submit = SubmitField("Save Changes", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ REGISTER FORM ------

class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign up", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ LOGIN FORM ------

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in", render_kw={"style": "margin-top: 25px;"})


# ------ END ------


# ------ COMMENT FORM ------

class CommentForm(FlaskForm):
    comment = CKEditorField("Comment", validators=[DataRequired()])
    submit = SubmitField("Submit Comment", render_kw={"style": "margin-top: 20px;"})


# ------ END ------

# ------------------ END BLOCK ------------------


# ------------------ PAGES BLOCK ------------------

@app.route('/')
def home():
    data = get_data()
    if any(data):
        title = data["website_configuration"]["homepage_title"]
        subtitle = data["website_configuration"]["homepage_subtitle"]
    else:
        title = "A website."
        subtitle = "A fully-fledged website."
    return render_template("index.html", all_posts=get_posts()[:3], posts_count=len(get_posts()), current_id=1,
                           title=title, subtitle=subtitle, name=get_name(), background_image=get_background())


@app.route('/page/<int:page_id>')
def page(page_id):
    deleted = request.args.get('deleted')
    if deleted is False:
        blog_posts = get_posts()
        if page_id == 1:
            return redirect(url_for('home'))
        result = page_id * 3
        posts = blog_posts[result - 3:result]
        count = 0
        for _ in posts:
            count += 1
    else:
        blog_posts = get_deleted()
        if page_id == 1:
            return redirect(url_for('deleted_posts'))
        result = page_id * 3
        posts = blog_posts[result - 3:result]
        count = 0
        for _ in posts:
            count += 1
    return render_template("index.html", all_posts=posts, posts_count=count, current_id=page_id, deleted=True,
                           name=get_name(),
                           background_image=get_background(), title="Deleted Posts",
                           subtitle="View and recover deleted posts!")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# ------------------ END BLOCK ------------------


# ------------------ POST SYSTEM BLOCK ------------------

@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    deleted = request.args.get('deleted')
    comment_page = request.args.get('c_page')
    form = CommentForm()
    if deleted is None:
        requested_post = BlogPost.query.get(post_id)
        post_comments = BlogPost.query.get(post_id).comments
    else:
        with open('deleted_posts.json', 'r') as data_file:
            requested_post = json.load(data_file)[post_id - 1]
            post_comments = requested_post["comments"]
    if comment_page is not None:
        current_c = comment_page
        if comment_page == 1:
            return redirect(url_for('show_post', post_id=post_id))
        try:
            result = int(comment_page) * 3
        except TypeError:
            return redirect(url_for('show_post', post_id=post_id))
        comment_items = post_comments[result - 3:result]
    else:
        current_c = 1
        if deleted is None:
            comment_items = requested_post.comments[:3]
        else:
            comment_items = requested_post["comments"][:3]

    count = 0
    for _ in comment_items:
        count += 1

    if form.validate_on_submit():
        now = dt.datetime.now()
        current_month = [month for month in months if now.month == month[0]][0][1]
        date = f'{current_month} {now.day}, {now.year}'
        new_comment = Comment(author=current_user,
                              parent_post=requested_post,
                              comment=form.comment.data,
                              date=date)
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, deleted=str(deleted),
                           name=get_name(), form=form, comments=comment_items, current_c=int(current_c), c_count=count)


@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    form = CreatePostForm(title=post.title,
                          subtitle=post.subtitle,
                          img_url=post.img_url,
                          body=post.body)
    if form.validate_on_submit():
        post.title = form.title.data
        post.subtitle = form.subtitle.data
        post.img_url = form.img_url.data
        post.body = form.body.data
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template('make-post.html', edit=True, post=post, form=form, name=get_name())


@app.route('/add', methods=['GET', 'POST'])
def add_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        now = dt.datetime.now()
        current_month = [month for month in months if now.month == month[0]][0][1]
        date = f'{current_month} {now.day}, {now.year}'
        new_post = BlogPost(title=form.title.data,
                            subtitle=form.subtitle.data,
                            author=current_user,
                            img_url=form.img_url.data,
                            body=form.body.data,
                            date=date)
        db.session.add(new_post)
        db.session.commit()  # TODO - account for integrity error
        return redirect(url_for('home'))
    return render_template('make-post.html', form=form, name=get_name())


@app.route('/deleted')
def deleted_posts():
    return render_template('index.html', deleted_posts=get_deleted()[:3], delete=True,
                           posts_count=len(get_deleted()), current_id=1, name=get_name(),
                           background_image=get_background(), title="Deleted Posts",
                           subtitle="View and recover deleted posts!")


@app.route('/delete/<int:post_id>')
def delete_post(post_id):
    post = BlogPost.query.get(post_id)
    lst = Comment.query.filter_by(post_id=post.id).all()
    try:
        with open('deleted_posts.json', 'r') as data_file:
            data = json.load(data_file)
            post_id = data[-1]["post_id"] + 1
    except FileNotFoundError:
        data = []
        post_id = 1
    except JSONDecodeError:
        data = []
        post_id = 1
    new_post = {
        "post_title": post.title,
        "author_id": post.author.id,
        "author": post.author.name,
        "subtitle": post.subtitle,
        "post_id": post_id,
        "img_url": post.img_url,
        "body": post.body,
        "date": post.date,
        "comments": [{"author_id": comment.author_id, "author": comment.author.name,
                      "author_email": comment.author.email, "post_id": comment.post_id, "comment": comment.comment,
                      "date": comment.date} for comment in lst]
    }
    data.append(new_post)
    with open('deleted_posts.json', 'w') as data_file:
        json.dump(data, data_file, indent=4)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/recover/<int:post_id>')
def recover_post(post_id):
    with open('deleted_posts.json', 'r') as data_file:
        data = json.load(data_file)
    post = data[post_id - 1]
    comments = data[post_id - 1]["comments"]
    new_post = BlogPost(author=User.query.get(post["author_id"]),
                        title=post["post_title"],
                        subtitle=post["subtitle"],
                        date=post["date"],
                        body=post["body"],
                        img_url=post["img_url"],
                        )
    db.session.add(new_post)
    comments = [db.session.add(Comment(author=User.query.filter_by(name=comment["author"]).first(),
                                       post_id=BlogPost.query.filter_by(title=post["post_title"]).first().id,
                                       parent_post=BlogPost.query.filter_by(title=post["post_title"]).first(),
                                       comment=comment["comment"], date=comment["date"])) for comment in comments]
    db.session.commit()
    return redirect(url_for('home'))


# ------ COMMENT SYSTEM ------

@app.route('/delete-comment/<int:comment_id>')
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    current_post = comment.post_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('show_post', post_id=current_post))


# ------ END ------


# ------------------ END BLOCK ------------------


# ------------------ SETTINGS ------------------

@app.route('/settings')
def settings():
    options = {"Website Configuration": {"desc": "Configure your website.",
                                         "func": "web_configuration"},
               'Contact Me Configuration': {"desc": 'Configure the "Contact Me" page.',
                                            "func": "web_configuration"},
               'About Me Configuration': {"desc": 'Configure the "About Me" page.',
                                          "func": "web_configuration"}}
    return render_template('index.html', settings=True, options=options,
                           options_count=len(list(options.keys())),
                           errors=check_errors(), title="Settings",
                           subtitle="Here you will be able to access primary website configurations.",
                           name=get_name(),
                           background_image=get_background())


@app.route('/web-configure', methods=['GET', 'POST'])
def web_configuration():
    try:
        with open('data.json', 'r') as data_file:
            data = json.load(data_file)
    except FileNotFoundError:
        data = {}
    except JSONDecodeError:
        data = {}
    if any(data.keys()):
        form = WebConfigForm(name=data["website_configuration"]['name'],
                             homepage_title=data["website_configuration"]['homepage_title'],
                             homepage_subtitle=data["website_configuration"]['homepage_subtitle'],
                             background_image=data["website_configuration"]['background_image'],
                             twitter_link=data["website_configuration"]['twitter_link'],
                             facebook_link=data["website_configuration"]['facebook_link'],
                             github_link=data["website_configuration"]['github_link'])
    else:
        form = WebConfigForm()
    if form.validate_on_submit():
        new_data = {"website_configuration": {
            "name": form.name.data,
            "homepage_title": form.homepage_title.data,
            "homepage_subtitle": form.homepage_subtitle.data,
            "background_image": form.background_image.data,
            "twitter_link": form.twitter_link.data,
            "facebook_link": form.facebook_link.data,
            "github_link": form.github_link.data
        }
        }
        data.update(new_data)
        with open('data.json', 'w') as data_file:
            json.dump(data, data_file, indent=4)
        return redirect(url_for('settings'))
    return render_template('config.html', config_title="Website Configuration",
                           config_desc="Configure primary website elements.", form=form,
                           config_func="web_configuration", name=get_name())


# ------------------ END BLOCK ------------------


# ------------------ AUTHENTICATION BLOCK ------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        password = generate_password_hash(password=form.password.data,
                                          method='pbkdf2:sha256', salt_length=8)
        new_user = User(email=form.email.data,
                        password=password, name=form.name.data)
        db.session.add(new_user)
        try:
            db.session.commit()
        except IntegrityError:
            flash("This email already exists, log in instead!")
            return redirect(url_for('login'))
        login_user(User.query.filter_by(email=form.email.data).first())
        return redirect(url_for('home'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash("Incorrect password, please try again.")
        else:
            flash("This email does not exist, please try again.")
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# ------------------ END BLOCK ------------------


# ------------------ SERVER CONFIG ------------------

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
