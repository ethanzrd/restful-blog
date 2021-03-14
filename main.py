# TODO ------------------ TODO BLOCK ------------------

# TODO - Use NJSON as database for json files
# TODO - Verify contact support email before usage using confirmation links
# TODO - Check if HTTP requests match with configuration functions
# TODO - Create special account
# TODO - Set comment names to profile links

# ------------------ END BLOCK ------------------


# ------------------ IMPORTS BLOCK ------------------

from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_msearch import Search
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy.orm import relationship
from wtforms import StringField, SubmitField, PasswordField, SelectField
from wtforms.validators import DataRequired, URL, Email
from flask_ckeditor import CKEditor, CKEditorField
import datetime as dt
from flask_mail import Mail, Message
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import UnmappedInstanceError
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_gravatar import Gravatar
import os
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import html2text
from sqlalchemy.dialects.postgresql import JSON

# ------------------ END BLOCK ------------------


# ------------------ APPLICATION CONFIG BLOCK ------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
months = [(i, dt.date(2008, i, 1).strftime('%B')) for i in range(1, 13)]
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["MAIL_SERVER"] = 'smtp.gmail.com'
app.config["MAIL_PORT"] = 587
app.config["MAIL_USERNAME"] = os.environ.get('EMAIL')
app.config['MAIL_PASSWORD'] = os.environ.get('PASSWORD')
app.config['MAIL_USE_TLS'] = True
EMAIL = os.environ.get('EMAIL')
db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)
search = Search()
search.init_app(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])


# ------------------ END BLOCK ------------------

# ------------------ USER CONFIG ------------------

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __searchable__ = ['name']
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    confirmed_email = db.Column(db.Boolean(), default=False)
    join_date = db.Column(db.String(300), default='')
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    admin = db.Column(db.Boolean(), default=False)
    author = db.Column(db.Boolean(), default=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")


# ------------------ DATABASE CONFIG ------------------

# ------ BLOG POSTS TABLE ------

class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    __searchable__ = ["title", "subtitle"]
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(400), nullable=False)
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

class DeletedPost(db.Model):
    __tablename__ = 'deleted_posts'
    id = db.Column(db.Integer, primary_key=True)
    json_column = db.Column(JSON, nullable=False)


# ------ END ------


# ------ DELETED POSTS TABLE ------

class Data(db.Model):
    __tablename__ = 'data_table'
    id = db.Column(db.Integer, primary_key=True)
    json_column = db.Column(JSON, nullable=False)


# ------ END ------

db.create_all()  # CREATE ALL TABLES


# ------------------ END ------------------


def get_posts():  # GET ALL EXISTING POSTS
    try:
        return BlogPost.query.all()
    except OperationalError:
        return []


def clean_posts():
    [db.session.delete(post) for post in DeletedPost.query.all()
     if User.query.filter_by(email=post.json_column["author_email"]).first() is None]
    for post in BlogPost.query.all():
        try:
            user = User.query.filter_by(email=post.author.email).first()
            if user is None:
                db.session.delete(post)
        except AttributeError:
            db.session.delete(post)
    for comment in Comment.query.all():
        try:
            comment = comment.author.email
        except (AttributeError, TypeError):
            db.session.delete(comment)


def generate_date():  # GET THE CURRENT DATE IN A STRING FORMAT
    now = dt.datetime.now()
    current_month = [month for month in months if now.month == month[0]][0][1]
    return f'{current_month} {now.day}, {now.year}'


def get_user_posts(user_id):  # GET ALL POSTS ASSIGNED TO USER BY USER ID
    try:
        return User.query.get(user_id).posts
    except AttributeError:
        return []


def get_user_comments(user_id):  # GET ALL COMMENTS ASSIGNED TO USER BY USER ID
    try:
        return User.query.get(user_id).comments
    except AttributeError:
        return []


def delete_notification(email, name, action_user, action_title, action_reason):
    msg = Message('Account Deleted', sender=EMAIL, recipients=[email])
    msg.body = f"Hello {name}, this is an automatic email from {get_name()} to notify you of recent" \
               f" events that occurred in regards to your account.\n\n" \
               f'Your account was deleted by {action_user} due to "{action_title}".\n\n' \
               f'Deletion reasoning by actioning staff member:\n\n{html2text.html2text(action_reason)}\n\n' \
               f'If you believe that a mistake was made, contact us by replying to this email or via our website.'
    mail.send(msg)


def set_notification(category, email, name, action_user, action_reason):
    try:
        support_email = get_data()["contact-configuration"]["support_email"]
    except KeyError:
        msg = Message(f'Account set as {category}', sender=EMAIL, recipients=[email])
    else:
        msg = Message(f'Account set as {category}', sender=EMAIL, recipients=[email,
                                                                                                       support_email])
    msg.body = f"Hello {name}, this is an automatic email from {get_name()} to notify you of recent" \
               f" events that occurred in regards to your account.\n\n" \
               f'Your account was set as an {category} by {action_user}.\n\n' \
               f'Reasoning by actioning staff member:\n\n{html2text.html2text(action_reason)}\n\n' \
               f'Congratulations, if you have any inquires, contact us by replying to this email or via our website.'
    mail.send(msg)


def remove_notification(category, email, name, action_user, action_reason):
    try:
        support_email = get_data()["contact-configuration"]["support_email"]
    except KeyError:
        msg = Message(f'Account removed as {category}', sender=EMAIL, recipients=[email])
    else:
        msg = Message(f'Account removed as {category}', sender=EMAIL, recipients=[email,
                                                                                                           support_email])
    msg.body = f"Hello {name}, this is an automatic email from {get_name()} to notify you of recent" \
               f" events that occurred in regards to your account.\n\n" \
               f'Your account was removed as an {category} by {action_user}.\n\n' \
               f'Reasoning by actioning staff member:\n\n{html2text.html2text(action_reason)}\n\n' \
               f'If you believe that a mistake was made, contact us by replying to this email or via our website.'
    mail.send(msg)


def contact_notification(email, name, action_reason):
    try:
        support_email = get_data()["contact_configuration"]["support_email"]
    except KeyError:
        return False
    msg = Message(f"{get_name()} - Contact Inquiry", sender=EMAIL, recipients=[support_email])
    msg.body = f"This is an automatic email from {get_name()} to notify you of a" \
               f" user inquiry.\n\n" \
               f'Name: {name}\n\n' \
               f'Email: {email}\n\n' \
               f'Message:\n\n{html2text.html2text(action_reason)}' \
               f'Note: This email was set as a support email for {get_name()}, if you are not familiar with the' \
               f' source of this email, please contact us by replying to this email or via our website.'
    mail.send(msg)


def redirect_http():
    if current_user.is_authenticated is False:
        return abort(403)
    if current_user.admin is False and current_user.author is False:
        return abort(403)
    return None


def admin_redirect():
    if current_user.is_authenticated is False or current_user.admin is False:
        return abort(403)


def get_admin_count():  # GET THE AMOUNT OF ADMINISTRATORS
    return len([user for user in User.query.all() if user.admin is True])


def get_deleted():
    return [(post.id, post.json_column) for post in DeletedPost.query.all()]


def get_data(homepage=False):  # GET CONFIG DATA
    def set_default():
        default_data = {"secret_password": generate_password_hash(password="default",
                                                                  method='pbkdf2:sha256', salt_length=8),
                        "website_configuration": {
                            "name": "Website",
                            "homepage_title": "A website",
                            "homepage_subtitle": "A fully fledged website",
                            "background_image": "https://www.panggi.com/images/featured/python.png",
                            "twitter_link": "https://www.twitter.com",
                            "facebook_link": "https://www.facebook.com",
                            "github_link": "https://www.github.com"
                        },
                        "contact_configuration": {
                            "page_heading": "Contact us",
                            "page_subheading": "Contact us, and we'll respond as soon as we can.",
                            "page_description": "With the current workload, we are able to respond within 24 hours.",
                            "background_image": "https://www.panggi.com/images/featured/python.png",
                            "support_email": EMAIL
                        },
                        "about_configuration": {
                            "page_heading": "About us",
                            "page_subheading": "About what we do.",
                            "background_image": "https://www.panggi.com/images/featured/python.png",
                            "page_content": "For now, this page remains empty."
                        }
                        }
        update_data(default_data)

    try:
        data = Data.query.all()[0].json_column
        if homepage:
            title = data["website_configuration"]["homepage_title"]
            subtitle = data["website_configuration"]["homepage_subtitle"]
            return title, subtitle
        else:
            return data
    except (KeyError, TypeError, OperationalError):
        if homepage:
            title = "A website."
            subtitle = "A fully-fledged website."
            return title, subtitle
        else:
            return {}
    except (AttributeError, IndexError):
        set_default()
        if homepage:
            get_data(homepage=True)
        else:
            get_data()
        return redirect(url_for("home"))


def update_data(given_data):  # UPDATE CONFIG DATA
    new_data = Data(json_column=given_data)
    if len(Data.query.all()) > 0 and Data.query.all()[0] is not None:
        db.session.delete(Data.query.all()[0])
    db.session.add(new_data)
    db.session.commit()


def check_errors():  # CHECK FOR ERRORS IN DATA
    errors = {}

    # ------ TEST 1, CHECK IF DATA FILE IS EMPTY ------

    try:
        test = Data.query.all()[0].json_column
    except (AttributeError, IndexError):
        errors["Data File"] = "Data file is empty, no website configurations available."
    else:
        if check_password_hash(test['secret_password'], 'default'):
            errors["Authentication Password"] = "Authentication Password is set to default, change it immediately."

    # ------ TEST END ------

    return errors


def get_name():
    data = get_data()
    try:
        return data["website_configuration"]["name"]
    except (TypeError, IndexError, KeyError):
        return "Website"


def get_background(configuration="none"):
    try:
        return get_data()[configuration]["background_image"]
    except (KeyError, TypeError):
        return ""


# ------------------ END BLOCK ------------------

# ------------------ ERROR HANDLERS ------------------

@app.errorhandler(401)
def unauthorized(e):
    return render_template('http-error.html', background_image=get_background('website_configuration'),
                           error="401 - Unauthorized", error_description="You're unauthorized to perform this action.",
                           name=get_name()), 401


@app.errorhandler(403)
def forbidden(e):
    return render_template('http-error.html', background_image=get_background('website_configuration'),
                           error="403 - Forbidden", error_description="You're unauthorized to perform this action.",
                           name=get_name()), 403


@app.errorhandler(404)
def unauthorized(e):
    return render_template('http-error.html', background_image=get_background('website_configuration'),
                           error="404 - Page Not Found", error_description="Page not found.",
                           name=get_name()), 404


# ------------------ END ------------------


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
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign up", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ LOGIN FORM ------

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in", render_kw={"style": "margin-top: 25px;"})


# ------ END ------

# ------ CONTACT FORM ------

class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    message = CKEditorField("Your Message", validators=[DataRequired()])
    submit = SubmitField("Send", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ COMMENT FORM ------

class CommentForm(FlaskForm):
    comment = CKEditorField("Comment", validators=[DataRequired()])
    submit = SubmitField("Submit Comment", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ SEARCH FORM ------

class SearchForm(FlaskForm):
    category = SelectField("Category", choices=[('posts', 'Posts'), ('users', 'Users')])
    search = StringField("Search", validators=[DataRequired()])
    submit = SubmitField("Search", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ DELETION REPORT FORM ------

class DeleteForm(FlaskForm):
    title = StringField("Action Title", validators=[DataRequired()])
    reason = CKEditorField("Action Reason", validators=[DataRequired()])
    submit = SubmitField("Delete Account", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ DELETION REPORT FORM ------

class AuthForm(FlaskForm):
    code = PasswordField("Authorization Code", validators=[DataRequired()])
    submit = SubmitField("Authenticate", render_kw={"style": "margin-top: 20px;"})


# ------ END ------

# ------ CONTACT CONFIG FORM ------

class ContactConfigForm(FlaskForm):
    page_heading = StringField("Contact Page Title", validators=[DataRequired()])
    page_subheading = StringField("Contact Page Subtitle", validators=[DataRequired()])
    page_description = StringField("Contact Page Description", validators=[DataRequired()])
    background_image = StringField("Contact Page Background Image", validators=[URL()])
    support_email = StringField("Contact Support Email (Inquires will be directed to the specified email)",
                                validators=[DataRequired(), Email()])
    submit = SubmitField("Save changes", render_kw={"style": "margin-top: 20px;"})


# ------ END ------

# ------ CONTACT CONFIG FORM ------

class AboutConfigForm(FlaskForm):
    page_heading = StringField("About Page Title", validators=[DataRequired()])
    page_subheading = StringField("About Page Subtitle", validators=[DataRequired()])
    background_image = StringField("Contact Page Background Image", validators=[URL()])
    page_content = CKEditorField("About Page Content", validators=[DataRequired()])
    submit = SubmitField("Save changes", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ MAKE ADMINISTRATOR FORM ------

class MakeUserForm(FlaskForm):
    reason = CKEditorField("Reason for Action", validators=[DataRequired()])
    submit = SubmitField("Proceed", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ AUTHENTICATION CONFIG FORM ------

class AuthConfig(FlaskForm):
    old_password = PasswordField("Old Authentication Password", validators=[DataRequired()])
    new_password = PasswordField("New Authentication Password", validators=[DataRequired()])
    submit = SubmitField("Change Authentication Password", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------------------ END BLOCK ------------------


# ------------------ PAGES BLOCK ------------------

@app.route('/')
def home():
    data = get_data(homepage=True)
    return render_template("index.html", all_posts=get_posts()[:3], posts_count=len(get_posts()), current_id=1,
                           title=data[0], subtitle=data[1], name=get_name(),
                           background_image=get_background("website_configuration"))


@app.route('/page/<int:page_id>')
def page(page_id):
    deleted = request.args.get('deleted')
    user_id = request.args.get('user_id')
    current_mode = request.args.get('current_mode')
    data = get_data(homepage=True)
    if deleted == 'True':
        blog_posts = get_deleted()
        if page_id == 1:
            return redirect(url_for('deleted_posts'))
        result = page_id * 3
        posts = blog_posts[result - 3:result]
        count = 0
        for _ in posts:
            count += 1
        return render_template('index.html', deleted_posts=posts, deleted='True',
                               posts_count=count, current_id=page_id, name=get_name(),
                               background_image=get_background('website_configuration'), title="Deleted Posts",
                               subtitle="View and recover deleted posts!")
    elif user_id is not None and User.query.get(user_id) is not None:
        user = User.query.get(user_id)
        posts = get_user_posts(user_id)
        comments = get_user_comments(user_id)
        if current_mode in ['posts', 'comments']:
            if current_mode == 'posts':
                blog_posts = posts
                if page_id == 1:
                    return redirect(url_for('user_page', user_id=user_id))
                result = page_id * 3
                posts = blog_posts[result - 3:result]
                count = 0
                for _ in posts:
                    count += 1
                return render_template("user.html", all_posts=posts, posts_count=count, current_id=page_id,
                                       title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Posts",
                                       name=get_name(),
                                       background_image=get_background('website_configuration'), current_mode='posts',
                                       user=user)
            else:
                blog_posts = comments
                if page_id == 1:
                    return redirect(url_for('user_page', user_id=user_id, current_mode='comments'))
                result = page_id * 3
                posts = blog_posts[result - 3:result]
                count = 0
                for _ in posts:
                    count += 1
                return render_template("user.html", comments=posts, posts_count=count,
                                       current_id=page_id,
                                       title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Comments",
                                       name=get_name(),
                                       background_image=get_background('website_configuration'),
                                       current_mode='comments', user=user)
        else:
            flash("Malformed page request for user profile.")
            return redirect(url_for('home'))
    else:
        blog_posts = get_posts()
        if page_id == 1:
            return redirect(url_for('home'))
        result = page_id * 3
        posts = blog_posts[result - 3:result]
        count = 0
        for _ in posts:
            count += 1
    return render_template("index.html", all_posts=posts, posts_count=count, current_id=page_id,
                           name=get_name(),
                           background_image=get_background('website_configuration'), title=data[0],
                           subtitle=data[1])


@app.route("/about")
def about():
    try:
        about_config = get_data()['about_configuration']
    except KeyError:
        heading = "About us"
        subheading = "About what we do."
        content = "For now, this page remains empty."
    else:
        heading = about_config['page_heading']
        subheading = about_config['page_subheading']
        content = about_config['page_content']
    return render_template("about.html", heading=heading, subheading=subheading, content=content,
                           background_image=get_background('about_configuration'), name=get_name())


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    valid = True
    try:
        support_email = get_data()["contact_configuration"]["support_email"]
    except KeyError:
        flash("Warning | No support email specified, messages will not be received.")
        valid = False
    try:
        contact_config = get_data()['contact_configuration']
    except KeyError:
        heading = "Contact us"
        subheading = "We'll get to you as soon as we can."
        description = "Want to get in touch? Fill out the form below and we'll respond as soon as we can!"
    else:
        heading = contact_config['page_heading']
        subheading = contact_config['page_subheading']
        description = contact_config['page_description']
    if valid:
        if current_user.is_authenticated and current_user.confirmed_email:
            form = ContactForm(name=current_user.name, email=current_user.email)
        else:
            form = ContactForm()
        if form.validate_on_submit():
            notification = contact_notification(form.email.data, form.name.data, form.message.data)
            if notification is False:
                flash("No support email specified, unable to send your message.")
                return redirect(url_for('home'))
            else:
                flash("Message successfully sent.")
                return redirect(url_for('home'))
        return render_template("contact.html", form=form, heading=heading, subheading=subheading,
                               description=description,
                               background_image=get_background('contact_configuration'), name=get_name())
    return render_template("contact.html", heading=heading, subheading=subheading,
                           description=description,
                           background_image=get_background('contact_configuration'), name=get_name())


# ------------------ END BLOCK ------------------


# ------------------ POST SYSTEM BLOCK ------------------

@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchForm()
    if form.validate_on_submit():
        if form.category.data == 'posts':
            posts = BlogPost.query.msearch(form.search.data).all()
            return render_template("index.html", all_posts=posts[:3], posts_count=len(posts), current_id=1,
                                   title="Search Results",
                                   subtitle=f"Displaying post search results for: {form.search.data}",
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   search=True, mode='posts')
        else:
            users = [user for user in User.query.msearch(form.search.data).all() if user.confirmed_email is True]
            return render_template("index.html", results=users[:3], posts_count=len(users), current_id=1,
                                   title="Search Results",
                                   subtitle=f"Displaying user search results for: {form.search.data}",
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   search=True, mode='users')
    return render_template('search.html', form=form, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    deleted = request.args.get('deleted')
    comment_page = request.args.get('c_page')
    form = CommentForm()
    if deleted is None:
        requested_post = BlogPost.query.get(post_id)
        post_comments = BlogPost.query.get(post_id).comments
    else:
        try:
            requested_post = (DeletedPost.query.get(post_id).id, DeletedPost.query.get(post_id).json_column)
        except AttributeError:
            flash("Could not find a post with the specified ID.")
            return redirect(url_for('deleted_posts'))
        post_comments = requested_post[1]["comments"]
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
            comment_items = requested_post[1]["comments"][:3]

    count = 0
    for _ in comment_items:
        count += 1

    if form.validate_on_submit():
        if current_user.is_authenticated:
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
        else:
            flash("User is not logged in.")
            return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, deleted=str(deleted),
                           name=get_name(), form=form, comments=comment_items, current_c=int(current_c), c_count=count)


@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    redirect_http()
    post = BlogPost.query.get(post_id)
    if post is not None:
        if post.author.email == current_user.email:
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
        else:
            return abort(403)
    else:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('home'))


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_post():
    redirect_http()
    form = CreatePostForm()
    if form.validate_on_submit():
        date = generate_date()
        new_post = BlogPost(title=form.title.data,
                            subtitle=form.subtitle.data,
                            author=current_user,
                            img_url=form.img_url.data,
                            body=form.body.data,
                            date=date)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('make-post.html', form=form, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/deleted')
@login_required
def deleted_posts():
    redirect_http()
    posts = get_deleted()[:3]
    return render_template('index.html', deleted_posts=posts,
                           deleted="True",
                           posts_count=len(posts), current_id=1, name=get_name(),
                           background_image=get_background('website_configuration'), title="Deleted Posts",
                           subtitle="View and recover deleted posts!")


@app.route('/delete/<int:post_id>')
@login_required
def delete_post(post_id):
    redirect_http()
    post = BlogPost.query.get(post_id)
    if post is not None:
        if current_user.is_authenticated and current_user.author is True and post.author.email == current_user.email or current_user.is_authenticated and current_user.admin is True:
            try:
                lst = Comment.query.filter_by(post_id=post.id).all()
            except AttributeError:
                flash("Could not find a post with the specified ID.")
                return redirect(url_for('deleted_posts'))
            new_post = {
                "post_title": post.title,
                "author_id": post.author.id,
                "author_email": post.author.email,
                "author": post.author.name,
                "subtitle": post.subtitle,
                "img_url": post.img_url,
                "body": post.body,
                "date": post.date,
                "comments": [{"author_id": comment.author_id, "author": comment.author.name,
                              "author_email": comment.author.email, "post_id": comment.post_id, "comment": comment.comment,
                              "date": comment.date} for comment in lst]
            }
            new_deleted = DeletedPost(json_column=new_post)
            db.session.add(new_deleted)
            [db.session.delete(comment) for comment in lst]
            db.session.delete(post)
            db.session.commit()
            return redirect(url_for('home'))
        else:
            return abort(403)
    else:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))


@app.route('/recover/<int:post_id>')
@login_required
def recover_post(post_id):
    redirect_http()
    try:
        actual = DeletedPost.query.get(post_id)
        post = actual.json_column
    except AttributeError:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))
    try:
        if current_user.email != post["author_email"] or current_user.author is False and current_user.admin is False:
            return abort(403)
    except AttributeError:
        flash("The author could not be found.")
        return redirect(url_for('deleted_posts'))
    comments = post["comments"]
    new_post = BlogPost(author=User.query.filter_by(email=post["author_email"]).first(),
                        title=post["post_title"],
                        subtitle=post["subtitle"],
                        date=post["date"],
                        body=post["body"],
                        img_url=post["img_url"],
                        )
    db.session.add(new_post)
    [db.session.add(Comment(author=User.query.filter_by(email=comment["author_email"]).first(),
                            post_id=new_post.id,
                            parent_post=new_post,
                            comment=comment["comment"], date=comment["date"])) for comment in comments]
    db.session.delete(actual)
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/perm-delete/<int:post_id>')
def perm_delete(post_id):
    admin_redirect()
    try:
        actual_post = DeletedPost.query.get(post_id)
        post = actual_post.json_column
    except AttributeError:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))
    try:
        db.session.delete(actual_post)
    except UnmappedInstanceError:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))
    db.session.commit()
    return redirect(url_for('deleted_posts'))


# ------ COMMENT SYSTEM ------


@app.route('/delete-comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    if comment is not None:
        if comment.parent_post.author.email == current_user.email or current_user.email == comment.author.email:
            current_post = comment.post_id
            db.session.delete(comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=current_post))
        else:
            return abort(403)
    else:
        flash("Could not find a comment with the specified ID.")
        return redirect(url_for('home'))


# ------ END ------


# ------------------ END BLOCK ------------------


# ------------------ SETTINGS ------------------

@app.route('/settings')
@login_required
def settings():
    admin_redirect()
    options = {"Website Configuration": {"desc": "Configure your website.",
                                         "func": "web_configuration"},
               'Contact Me Configuration': {"desc": 'Configure the "Contact Me" page.',
                                            "func": "contact_configuration"},
               'About Me Configuration': {"desc": 'Configure the "About Me" page.',
                                          "func": "about_configuration"},
               'Authentication Configuration': {"desc": "Configure the website's authentication system.",
                                                "func": "authentication_configuration"}}
    return render_template('index.html', settings=True, options=options,
                           options_count=len(list(options.keys())),
                           errors=check_errors(), title="Settings",
                           subtitle="Here you will be able to access primary website configurations.",
                           name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/web-configure', methods=['GET', 'POST'])
@login_required
def web_configuration():
    admin_redirect()
    data = get_data()
    try:
        config_data = data['website_configuration']
        form = WebConfigForm(name=config_data['name'],
                             homepage_title=config_data['homepage_title'],
                             homepage_subtitle=config_data['homepage_subtitle'],
                             background_image=config_data['background_image'],
                             twitter_link=config_data['twitter_link'],
                             facebook_link=config_data['facebook_link'],
                             github_link=config_data['github_link'])
    except KeyError:
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
        update_data(data)
        return redirect(url_for('settings'))
    return render_template('config.html', config_title="Website Configuration",
                           config_desc="Configure primary website elements.", form=form,
                           config_func="web_configuration", name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/contact-configure', methods=['GET', 'POST'])
@login_required
def contact_configuration():
    admin_redirect()
    data = get_data()
    try:
        config_data = data['contact_configuration']
        form = ContactConfigForm(page_heading=config_data['page_heading'],
                                 page_subheading=config_data['page_subheading'],
                                 page_description=config_data['page_description'],
                                 background_image=config_data['background_image'],
                                 support_email=config_data['support_email'])
    except KeyError:
        form = ContactConfigForm()
    if form.validate_on_submit():
        new_data = {"contact_configuration": {
            "page_heading": form.page_heading.data,
            "page_subheading": form.page_subheading.data,
            "page_description": form.page_description.data,
            "background_image": form.background_image.data,
            "support_email": form.support_email.data
        }
        }
        data.update(new_data)
        update_data(data)
        return redirect(url_for('settings'))
    return render_template('config.html', config_title="Contact Page Configuration",
                           config_desc="Configure primary elements of the contact page.", form=form,
                           config_func="contact_configuration", name=get_name(),
                           background_image=get_background('contact_configuration'))


@app.route('/about-configure', methods=['GET', 'POST'])
@login_required
def about_configuration():
    admin_redirect()
    data = get_data()
    try:
        config_data = data['about_configuration']
        form = AboutConfigForm(page_heading=config_data['page_heading'],
                               page_subheading=config_data['page_subheading'],
                               background_image=config_data['background_image'],
                               page_content=config_data['page_content'])
    except KeyError:
        form = AboutConfigForm()
    if form.validate_on_submit():
        new_data = {"about_configuration": {
            "page_heading": form.page_heading.data,
            "page_subheading": form.page_heading.data,
            "page_content": form.page_content.data
        }
        }
        data.update(new_data)
        update_data(data)
        return redirect(url_for('settings'))
    return render_template('config.html', config_title="About Page Configuration",
                           config_desc="Configure primary elements of the about page.", form=form,
                           config_func="about_configuration", name=get_name(),
                           background_image=get_background('about_configuration'))


@app.route('/auth-configure', methods=['GET', 'POST'])
@login_required
def authentication_configuration():
    admin_redirect()
    form = AuthConfig()
    data = get_data()
    try:
        config_data = data['secret_password']
    except KeyError:
        config_data = None
    if form.validate_on_submit():
        if config_data is not None:
            try:
                if check_password_hash(config_data, form.old_password.data):
                    new_password = generate_password_hash(password=form.new_password.data,
                                                          method='pbkdf2:sha256', salt_length=8)
                    new_data = {"secret_password": new_password}
                    data.update(new_data)
                    update_data(data)
                    return redirect(url_for('settings'))
                else:
                    flash("Incorrect authentication password.")
            except TypeError:
                flash("An unexpected error occurred during verification handling.")
        else:
            new_password = generate_password_hash(password=form.new_password.data,
                                                  method='pbkdf2:sha256', salt_length=8)
            new_data = {"secret_password": new_password}
            data.update(new_data)
            update_data(data)
            return redirect(url_for('settings'))
    return render_template('config.html', config_title="Authentication Configuration",
                           config_desc="Configure primary elements of the website's authentication", form=form,
                           config_func="authentication_configuration", name=get_name(),
                           background_image=get_background('website_configuration'))


# ------------------ END BLOCK ------------------


# ------------------ USER BLOCK ------------------

@app.route('/admin/<int:user_id>', methods=['GET', 'POST'])
@login_required
def make_admin(user_id):
    if get_admin_count() > 0:
        admin_redirect()
    user = User.query.get(user_id)
    authorized = request.args.get('authorized')
    form = MakeUserForm()
    if user is not None:
        if user.admin is not True:
            if authorized != "True":
                return redirect(url_for('admin_auth', user_id=user_id))
            if form.validate_on_submit():
                set_notification('administrator', user.email, user.name, current_user.name, form.reason.data)
                user.author = False
                user.admin = True
                db.session.commit()
                flash("The user has been set as an administrator, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='admin')
        else:
            flash("This user is already an administrator.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/admin-remove/<int:user_id>', methods=['GET', 'POST'])
@login_required
def remove_admin(user_id):
    admin_redirect()
    user = User.query.get(user_id)
    authorized = request.args.get('authorized')
    form = MakeUserForm()
    if user is not None:
        if user.admin is True:
            if authorized != "True":
                return redirect(url_for('admin_auth', user_id=user_id, remove=True))
            if form.validate_on_submit():
                remove_notification('administrator', user.email, user.name, current_user.name, form.reason.data)
                user.admin = False
                db.session.commit()
                flash("The user has been removed as an administrator, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='admin', remove="True")
        else:
            flash("This user is not an administrator.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/author/<int:user_id>', methods=['GET', 'POST'])
@login_required
def make_author(user_id):
    admin_redirect()
    user = User.query.get(user_id)
    form = MakeUserForm()
    if user is not None:
        if user.author is not True:
            if form.validate_on_submit():
                set_notification('author', user.email, user.name, current_user.name, form.reason.data)
                user.author = True
                db.session.commit()
                flash("This user has been set as an author, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='author')
        else:
            flash("This user is already set as an author.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/author-remove/<int:user_id>', methods=['GET', 'POST'])
@login_required
def remove_author(user_id):
    admin_redirect()
    user = User.query.get(user_id)
    form = MakeUserForm()
    if user is not None:
        if user.author is True:
            if form.validate_on_submit():
                remove_notification('author', user.email, user.name, current_user.name, form.reason.data)
                user.author = False
                db.session.commit()
                flash("This user has been removed as an author, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='author', remove="True")
        else:
            flash("This user is not an author.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/user/<int:user_id>')
def user_page(user_id):
    user = User.query.get(user_id)
    posts = get_user_posts(user_id)
    comments = get_user_comments(user_id)
    current_mode = request.args.get('current_mode')
    admin_count = get_admin_count()
    if user is not None:
        if current_mode == 'comments':
            return render_template("user.html", comments=comments[:3], posts_count=len(comments[:3]), current_id=1,
                                   title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Comments", name=get_name(),
                                   background_image=get_background('website_configuration'), current_mode='comments',
                                   user=user,
                                   admin_count=admin_count)
        else:
            return render_template("user.html", all_posts=posts[:3], posts_count=len(posts[:3]), current_id=1,
                                   title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Posts", name=get_name(),
                                   background_image=get_background('website_configuration'), current_mode='posts',
                                   user=user,
                                   admin_count=admin_count)
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/delete-user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def delete_user(user_id):
    admin_redirect()
    user = User.query.get(user_id)
    authorized = request.args.get('authorized')
    if user is not None:
        if user.admin is True and authorized != "True":
            return redirect(url_for('authorization', user_id=user_id))
        form = DeleteForm()
        if form.validate_on_submit():
            email = user.email
            delete_notification(email=user.email, name=user.name, action_user=current_user.name,
                                action_title=form.title.data, action_reason=form.reason.data)
            if current_user == user:
                logout_user()
            flash("The user has been deleted, a notification has been sent to the user.")
            db.session.delete(user)
            clean_posts()
            db.session.commit()
            return redirect(url_for('home'))
        return render_template('delete.html', form=form, user_id=user_id, name=get_name(), user_name=user.name,
                               background_image=get_background('website_configuration'))
    else:
        flash("This user does not exist.")
        return redirect(url_for('home'))


@app.route('/auth', methods=['GET', 'POST'])
@login_required
def authorization():
    admin_redirect()
    form = AuthForm()
    user_id = request.args.get('user_id')
    if User.query.get(user_id) is None:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))
    if form.validate_on_submit():
        try:
            contents = get_data()
            secret_password = contents['secret_password']
        except (KeyError, TypeError, IndexError):
            flash("Authentication Password is not available. Deletion cannot be performed at this time.")
            return redirect(url_for('home'))
        if check_password_hash(secret_password, form.code.data):
            return redirect(url_for('delete_user', user_id=user_id, authorized=True))
        else:
            flash("Incorrect authorization code.")
    return render_template('delete.html', form=form, authorization=True, user_id=user_id, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/admin-auth', methods=['GET', 'POST'])
@login_required
def admin_auth():
    if get_admin_count() > 0:
        admin_redirect()
    form = AuthForm()
    remove = request.args.get('remove')
    user_id = request.args.get('user_id')
    if User.query.get(user_id) is None:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))
    if form.validate_on_submit():
        contents = get_data()
        try:
            secret_password = contents['secret_password']
        except (TypeError, KeyError, IndexError):
            flash("Cannot retrieve Authentication Password, cannot set user as an administrator in this time.")
            return redirect(url_for('home'))
        if not contents:
            flash("Data File is not available, cannot retrieve authentication password."
                  " Cannot set user as an administrator in this time.")
            return redirect(url_for('home'))
        if check_password_hash(secret_password, form.code.data):
            if remove != 'True':
                return redirect(url_for('make_admin', user_id=user_id, authorized=True))
            else:
                return redirect(url_for('remove_admin', user_id=user_id, authorized=True))
        else:
            flash("Incorrect authorization code.")
    return render_template('admin-form.html', form=form, authorization=True, user_id=user_id, name=get_name(),
                           background_image=get_background('website_configuration'), category='admin',
                           remove=remove)


# ------------------ END BLOCK ------------------


# ------------------ AUTHENTICATION BLOCK ------------------

def verify_user(email, name):
    token = serializer.dumps(email, salt='email-verify')
    msg = Message('Confirmation Email', sender=EMAIL, recipients=[email])
    link = url_for('verify_email', token=token, email=email, _external=True)
    msg.body = f"Hello {name}, please go to this link to finalize your registration.\n\n" \
               f"{link}\n\nNote: If you're unfamiliar with the source of this email, simply ignore it."
    mail.send(msg)
    flash("A confirmation email has been sent to you.")
    return redirect(url_for('home'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            password = generate_password_hash(password=form.password.data,
                                              method='pbkdf2:sha256', salt_length=8)
            new_user = User(email=form.email.data,
                            password=password, name=form.name.data)
            db.session.add(new_user)
            db.session.commit()
            verify_user(form.email.data, form.name.data)
            return redirect(url_for('home'))
        else:
            if user.confirmed_email is True:
                flash("This email already exists, please try again.")
            else:
                db.session.delete(user)
                db.session.commit()
                password = generate_password_hash(password=form.password.data,
                                                  method='pbkdf2:sha256', salt_length=8)
                new_user = User(email=form.email.data,
                                password=password, name=form.name.data)
                db.session.add(new_user)
                db.session.commit()
                verify_user(form.email.data, form.name.data)
                return redirect(url_for('home'))

            return redirect(url_for('register'))
    return render_template('register.html', form=form, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/verify/<token>')
def verify_email(token):
    email = request.args.get('email')
    try:
        confirmation = serializer.loads(token, salt='email-verify', max_age=300)
    except SignatureExpired:
        flash("The token is expired, please try again.")
        return redirect(url_for('register'))
    except BadTimeSignature:
        flash("Incorrect token, please try again.")
        return redirect(url_for('register'))
    else:
        user = User.query.filter_by(email=email).first()
        if user is not None:
            user.confirmed_email = True
            user.join_date = generate_date()
            db.session.commit()
            login_user(user)
            flash("You've confirmed your email successfully.")
            return redirect(url_for('home'))
        else:
            flash("This user does not exist.")
            return redirect(url_for('register'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    user_name = None
    email = None
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None:
            if user.confirmed_email is True:
                if check_password_hash(user.password, form.password.data):
                    login_user(user)
                    return redirect(url_for('home'))
                else:
                    flash("Incorrect password, please try again.")
            else:
                email = user.email
                user_name = user.name
                flash("unconfirmed")
        else:
            flash("This email does not exist, please try again.")
    return render_template("login.html", form=form, email=email, user_name=user_name, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/validate')
def validate():
    email = request.args.get('email')
    name = request.args.get('name')
    if name is None or email is None:
        flash("Malformed validation request to server.")
        return redirect(url_for('login'))
    else:
        return verify_user(email, name)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# ------------------ END BLOCK ------------------


# ------------------ SERVER CONFIG ------------------

if __name__ == "__main__":
    app.run(debug=True)
