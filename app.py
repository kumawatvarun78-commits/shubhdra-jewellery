import os, re, secrets, time
from datetime import datetime
from flask import (Flask, render_template, request, redirect, url_for, session,
                   abort, flash, Response)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
prod = os.environ.get("FLASK_ENV") == "production"
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-key"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE, "si.db")),
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=prod,
)
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE, "static", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
db = SQLAlchemy(app)
SITE_URL = os.environ.get("SITE_URL", "https://www.shubhdraimitationshivganj.com")

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(90), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    products = db.relationship("Product", backref="category")

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), index=True)
    description = db.Column(db.Text, default="")
    image = db.Column(db.String(200), default="")
    additional_images = db.Column(db.Text, default="")  # comma-separated filenames
    featured = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    @property
    def extras(self): return [i for i in (self.additional_images or "").split(",") if i]

class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Enquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product_ref = db.Column(db.String(150))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, default="")

DEFAULTS = {
    "whatsapp": "919999999999", "phone": "+919999999999",
    "instagram": "https://www.instagram.com/your_profile/",
    "maps": "https://maps.app.goo.gl/23K4M8fy5gRDAEar5", "address": "",
    "banner": "",
    "about": "Shubhdra Imitation Jawellary is a wholesale imitation jewellery business specialising in traditional Rajasthani and Rajwadi-style jewellery. We supply retailers, resellers, boutiques, jewellery shops and bulk buyers with premium-looking designs, a wide variety of collections and retailer-friendly pricing, built on reliable, long-term business relationships.",
}
def S():
    d = dict(DEFAULTS)
    d.update({s.key: s.value for s in Setting.query.all()})
    return d

def slugify(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "item"

MAGIC = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png", b"RIFF": "webp"}
def save_image(f):
    if not f or not f.filename: return ""
    head = f.stream.read(12); f.stream.seek(0)
    ext = next((e for m, e in MAGIC.items() if head.startswith(m)), None)
    if not ext or (ext == "webp" and head[8:12] != b"WEBP"):
        raise ValueError("Only JPG, PNG or WEBP images are allowed.")
    name = secrets.token_hex(10) + "." + ext
    f.save(os.path.join(UPLOAD_DIR, name)); return name

def img_url(n): return url_for("static", filename="uploads/" + n) if n else ""
app.jinja_env.globals["img_url"] = img_url

@app.before_request
def csrf():
    session.setdefault("csrf", secrets.token_hex(16))
    if request.method == "POST" and not secrets.compare_digest(request.form.get("csrf", ""), session["csrf"]):
        abort(400)
app.jinja_env.globals["csrf"] = lambda: session.get("csrf", "")

@app.after_request
def headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"; r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return r

def render(t, **k): return render_template(t, s=S(), cats=Category.query.filter_by(active=True).order_by(Category.name).all(), site=SITE_URL, **k)

# ---------- public ----------
@app.route("/")
def home():
    feat = Product.query.filter_by(active=True, featured=True).order_by(Product.updated_at.desc()).limit(8).all()
    return render("index.html", feat=feat)

@app.route("/collections")
def collections():
    q = request.args.get("q", "").strip()[:60]; cat = request.args.get("cat", ""); sort = request.args.get("sort", "new")
    qs = Product.query.filter_by(active=True)
    if cat:
        c = Category.query.filter_by(slug=cat).first()
        qs = qs.filter_by(category_id=c.id) if c else qs.filter(False)
    if q:
        like = f"%{q}%"; qs = qs.filter(db.or_(Product.name.ilike(like), Product.sku.ilike(like), Product.description.ilike(like)))
    qs = qs.order_by(Product.name if sort == "name" else Product.created_at.desc())
    return render("collections.html", products=qs.all(), q=q, cat=cat, sort=sort)

@app.route("/product/<sku>")
def product(sku):
    p = Product.query.filter_by(sku=sku, active=True).first_or_404()
    return render("product.html", p=p)

@app.route("/enquiry", methods=["POST"])
def enquiry():
    f = request.form
    if f.get("website"): return redirect(url_for("home"))  # honeypot
    name, phone = f.get("name", "").strip()[:100], re.sub(r"[^\d+ ]", "", f.get("phone", ""))[:20]
    if not name or len(phone) < 7:
        flash("Please enter your name and a valid phone number.", "err"); return redirect(url_for("home") + "#contact")
    ref = f.get("product", "").strip()[:150]
    p = Product.query.filter_by(sku=ref).first()
    db.session.add(Enquiry(customer_name=name, phone=phone, email=f.get("email", "")[:120], product_id=p.id if p else None,
                           product_ref=ref, message=f.get("message", "")[:2000])); db.session.commit()
    flash("Thank you. We have received your enquiry and will contact you shortly.", "ok")
    return redirect(url_for("home") + "#contact")

@app.route("/robots.txt")
def robots(): return Response(f"User-agent: *\nDisallow: /admin\nSitemap: {SITE_URL}/sitemap.xml\n", mimetype="text/plain")

@app.route("/sitemap.xml")
def sitemap():
    urls = [SITE_URL + "/", SITE_URL + "/collections"] + [f"{SITE_URL}/product/{p.sku}" for p in Product.query.filter_by(active=True)]
    x = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{x}</urlset>', mimetype="application/xml")

# ---------- admin ----------
def need_admin():
    if not session.get("admin"): abort(404)  # hide admin from non-admins

FAILS = {}
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"): return redirect(url_for("admin_products"))
    if request.method == "POST":
        ip = request.remote_addr; n, t = FAILS.get(ip, (0, 0))
        if n >= 5 and time.time() - t < 600: flash("Too many attempts. Try again in 10 minutes.", "err")
        else:
            u = AdminUser.query.filter_by(username=request.form.get("username", "")).first()
            if u and check_password_hash(u.password_hash, request.form.get("password", "")):
                session.clear(); session["admin"] = u.id; session["csrf"] = secrets.token_hex(16)
                return redirect(url_for("admin_products"))
            FAILS[ip] = (n + 1, time.time()); flash("Incorrect username or password.", "err")
    return render_template("admin.html", page="login", s=DEFAULTS)

@app.route("/admin/logout", methods=["POST"])
def admin_logout(): session.clear(); return redirect(url_for("admin_login"))

def arender(page, **k): return render_template("admin.html", page=page, s=S(), allcats=Category.query.order_by(Category.name).all(), **k)

@app.route("/admin/products")
def admin_products():
    need_admin(); return arender("products", products=Product.query.order_by(Product.created_at.desc()).all(),
                                 enquiries=Enquiry.query.order_by(Enquiry.created_at.desc()).limit(30).all())

@app.route("/admin/products/new", methods=["GET", "POST"])
@app.route("/admin/products/<int:pid>", methods=["GET", "POST"])
def admin_product(pid=None):
    need_admin(); p = db.get_or_404(Product, pid) if pid else None
    if request.method == "POST":
        f = request.form; name, sku = f.get("name", "").strip(), f.get("sku", "").strip().upper()
        if not name or not sku: flash("Name and product code are required.", "err")
        elif Product.query.filter(Product.sku == sku, Product.id != (p.id if p else 0)).first(): flash("That product code already exists.", "err")
        else:
            try:
                p = p or Product(); p.name, p.sku, p.description = name[:150], sku[:50], f.get("description", "")[:3000]
                p.category_id = int(f["category_id"]) if f.get("category_id") else None
                p.featured, p.active = bool(f.get("featured")), bool(f.get("active")); p.demo = bool(f.get("demo"))
                main = save_image(request.files.get("image"))
                if main: p.image = main
                ex = [save_image(x) for x in request.files.getlist("extras") if x.filename]
                keep = [i for i in p.extras if i not in f.getlist("remove")]
                p.additional_images = ",".join(keep + ex)
                db.session.add(p); db.session.commit(); flash("Product saved.", "ok"); return redirect(url_for("admin_products"))
            except ValueError as e: db.session.rollback(); flash(str(e), "err")
    return arender("product_form", p=p)

@app.route("/admin/products/<int:pid>/delete", methods=["POST"])
def admin_product_delete(pid):
    need_admin(); p = db.get_or_404(Product, pid)
    Enquiry.query.filter_by(product_id=pid).update({"product_id": None})
    files = [p.image] + p.extras; db.session.delete(p); db.session.commit()
    for fn in filter(None, files):
        try: os.remove(os.path.join(UPLOAD_DIR, fn))
        except OSError: pass
    flash("Product deleted.", "ok")
    return redirect(url_for("admin_products"))

@app.route("/admin/categories", methods=["GET", "POST"])
def admin_categories():
    need_admin()
    if request.method == "POST":
        a, f = request.form.get("action"), request.form
        if a == "add" and f.get("name", "").strip():
            n = f["name"].strip()[:80]
            if Category.query.filter_by(slug=slugify(n)).first(): flash("Category already exists.", "err")
            else: db.session.add(Category(name=n, slug=slugify(n))); flash("Category added.", "ok")
        elif a in ("edit", "delete"):
            c = db.get_or_404(Category, int(f.get("id", 0)))
            if a == "delete":
                for p in c.products: p.category_id = None
                db.session.delete(c); flash("Category deleted. Its products are now uncategorised.", "ok")
            else: c.name = f["name"].strip()[:80]; c.slug = slugify(c.name); c.active = bool(f.get("active")); flash("Category updated.", "ok")
        db.session.commit(); return redirect(url_for("admin_categories"))
    return arender("categories")

@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    need_admin()
    if request.method == "POST":
        try:
            for k in DEFAULTS:
                if k == "banner": continue
                v = request.form.get(k, "").strip()[:3000]
                if k in ("instagram", "maps") and v and not v.startswith("https://"): raise ValueError("Links must start with https://")
                db.session.merge(Setting(key=k, value=v))
            b = save_image(request.files.get("banner"))
            if b: db.session.merge(Setting(key="banner", value=b))
            if request.form.get("clear_banner"): db.session.merge(Setting(key="banner", value=""))
            db.session.commit(); flash("Website details saved.", "ok")
        except ValueError as e: db.session.rollback(); flash(str(e), "err")
        return redirect(url_for("admin_settings"))
    return arender("settings")

@app.route("/admin/password", methods=["POST"])
def admin_password():
    need_admin(); u = db.session.get(AdminUser, session["admin"]); new = request.form.get("new", "")
    if check_password_hash(u.password_hash, request.form.get("old", "")) and len(new) >= 10:
        u.password_hash = generate_password_hash(new); db.session.commit(); flash("Password changed.", "ok")
    else: flash("Old password is wrong or the new one is shorter than 10 characters.", "err")
    return redirect(url_for("admin_settings"))

# ---------- setup ----------
@app.cli.command("init-db")
def init_db():
    db.create_all()
    for n in ["Rajwadi Jewellery", "Rajasthani Jewellery", "Necklace Sets", "Earrings", "Bangles", "Bridal Jewellery",
              "Traditional Jewellery", "Pendant Sets", "Maang Tikka", "Nath", "Other Collections"]:
        if not Category.query.filter_by(slug=slugify(n)).first(): db.session.add(Category(name=n, slug=slugify(n)))
    db.session.commit()
    if not AdminUser.query.first():
        pw = os.environ.get("ADMIN_PASSWORD")
        if not pw or len(pw) < 10: raise SystemExit("Set ADMIN_PASSWORD (10+ characters) in the environment first.")
        db.session.add(AdminUser(username=os.environ.get("ADMIN_USERNAME", "admin"), password_hash=generate_password_hash(pw)))
    if not Product.query.first():
        g = lambda s: Category.query.filter_by(slug=s).first().id
        for i, (n, c, d) in enumerate([("Rajwadi Necklace Set", "necklace-sets", "Demo item. Replace with your real product."),
            ("Rajasthani Kundan Set", "rajasthani-jewellery", "Demo item. Replace with your real product."),
            ("Traditional Bridal Set", "bridal-jewellery", "Demo item. Replace with your real product."),
            ("Royal Earrings", "earrings", "Demo item. Replace with your real product.")], 1):
            db.session.add(Product(name=n, sku=f"DEMO-{i:03d}", category_id=g(c), description=d, featured=True, demo=True))
    db.session.commit(); print("Database ready.")
with app.app_context():
  db.create_all()
if __name__ == "__main__":
  app.run(debug=True)  
