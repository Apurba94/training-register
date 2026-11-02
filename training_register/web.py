"""The offline web app."""
from . import core
from .fieldkit import App, Fail, bar_chart, card, form, h, link, redirect, stats, table

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY, title TEXT NOT NULL, day TEXT NOT NULL, place TEXT NOT NULL DEFAULT '', sessions INTEGER NOT NULL DEFAULT 1, top REAL NOT NULL DEFAULT 100, pass_mark REAL NOT NULL DEFAULT 60);
CREATE TABLE IF NOT EXISTS people (id INTEGER PRIMARY KEY, course INTEGER NOT NULL REFERENCES courses(id), name TEXT NOT NULL, sex TEXT NOT NULL DEFAULT '', age_group TEXT NOT NULL DEFAULT '', pre REAL, post REAL, attended INTEGER NOT NULL DEFAULT 0, UNIQUE (course, name));
CREATE TABLE IF NOT EXISTS certificates (code TEXT PRIMARY KEY, name TEXT NOT NULL, course TEXT NOT NULL, day TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
"""


def create_app(db="training.db", organisation="Your organisation"):
    a = App("Training Register", db, SCHEMA, [("Courses", "/"), ("New course", "/new"), ("Check a certificate", "/verify")])
    if not a.one("SELECT value FROM settings WHERE key = 'secret'"):
        a.run("INSERT INTO settings (key, value) VALUES ('secret', ?)", core.new_secret())

    def secret():
        return a.one("SELECT value FROM settings WHERE key = 'secret'")

    def course_or_404(cid):
        c = a.row("SELECT * FROM courses WHERE id = ?", cid)
        if c is None:
            raise Fail("No such course", 404)
        return c

    @a.route("/")
    def home(req):
        rows = a.rows("SELECT c.*, COUNT(p.id) n FROM courses c LEFT JOIN people p ON p.course = c.id GROUP BY c.id ORDER BY c.day DESC")
        total = a.one("SELECT COUNT(*) FROM people")
        return a.page("Courses", stats([("Courses", len(rows)), ("Participants", total), ("Certificates", a.one("SELECT COUNT(*) FROM certificates WHERE revoked = 0"))]) + card("Courses", table(rows, [("Course", lambda r: link(f"/course/{r['id']}", r["title"])), ("Date", "day"), ("Place", "place"), ("People", "n")], "Create a course to begin.")))

    @a.route("/new", ("GET", "POST"))
    def new(req):
        if req.method == "POST":
            cur = a.run("INSERT INTO courses (title, day, place, sessions, top, pass_mark) VALUES (?, ?, ?, ?, ?, ?)", req.text("title"), req.date("day"), req.text("place", False), int(req.number("sessions", 1, 1, 500)), req.number("top", 100, 1), req.number("pass_mark", 60, 0))
            return redirect(f"/course/{cur.lastrowid}")
        return a.page("New course", card("Course", form(a, "/new", [("title", "Title"), ("day", "Date", "date"), ("place", "Place"), ("sessions", "Sessions", "number", 1), ("top", "Test marked out of", "number", 100), ("pass_mark", "Pass mark", "number", 60)], "Create")))

    @a.route("/course/<id>", ("GET", "POST"))
    def course(req, id):
        c = course_or_404(id)
        if req.method == "POST":
            opt = lambda k: req.number(k, low=0, high=c["top"]) if str(req.get(k)).strip() else None
            a.run("INSERT INTO people (course, name, sex, age_group, pre, post, attended) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(course, name) DO UPDATE SET sex = excluded.sex, age_group = excluded.age_group, pre = excluded.pre, post = excluded.post, attended = excluded.attended", id, req.text("name"), req.text("sex", False), req.text("age_group", False), opt("pre"), opt("post"), int(req.number("attended", 0, 0, c["sessions"])))
            return redirect(f"/course/{id}")
        people = a.rows("SELECT * FROM people WHERE course = ? ORDER BY name", id)
        pairs = [(p["pre"], p["post"]) for p in people if p["pre"] is not None and p["post"] is not None]
        s = core.paired_summary(pairs, c["top"])
        body = ""
        if s:
            body += stats([("Tested before and after", s["n"]), ("Before", f"{s['pre']:.1f}"), ("After", f"{s['post']:.1f}"), ("Learning gain", "n/a" if s["gain"] is None else f"{s['gain']:.2f} ({core.gain_label(s['gain'])})"), ("Improved", f"{s['improved']:.0%}")])
            if "p" in s:
                body += f'<p class="muted">Paired t-test p = {s["p"]:.3f}, effect size {s["effect"]:.2f}. Scores from one group, with no comparison group, cannot show that the course caused the change.</p>'
        results = {p["id"]: core.outcome(p["attended"], c["sessions"], p["post"], c["pass_mark"]) for p in people}
        body += card("Participants", table(people, [("Name", "name"), ("Sex", "sex"), ("Before", "pre"), ("After", "post"), ("Sessions", "attended"), ("Result", lambda p: results[p["id"]][1])], "No participants yet."))
        body += card("Add or update a participant", form(a, f"/course/{id}", [("name", "Name"), ("sex", "Sex", "select", [("", ""), ("F", "Female"), ("M", "Male"), ("O", "Other or not stated")]), ("age_group", "Age group"), ("pre", "Before score", "number"), ("post", "After score", "number"), ("attended", "Sessions attended", "number", 0)], "Save"))
        rep = core.reach([dict(p) | {"group": ""} for p in people])
        body += card("Who was reached", bar_chart(sorted(rep["by_sex"].items())))
        body += form(a, f"/course/{id}/issue", [], "Issue certificates to all who completed") + f'<p><a href="/course/{id}/certificates">View certificates</a></p>'
        return a.page(c["title"], body)

    @a.route("/course/<id>/issue", ("POST",))
    def issue(req, id):
        c = course_or_404(id)
        n = 0
        for p in a.rows("SELECT * FROM people WHERE course = ?", id):
            if core.outcome(p["attended"], c["sessions"], p["post"], c["pass_mark"])[0]:
                code = core.certificate_code(secret(), p["name"], c["title"], c["day"])
                n += a.run("INSERT OR IGNORE INTO certificates (code, name, course, day) VALUES (?, ?, ?, ?)", code, p["name"], c["title"], c["day"]).rowcount
        a.log("issue certificates", f"{id}: {n}")
        return redirect(f"/course/{id}/certificates")

    @a.route("/course/<id>/certificates")
    def certificates(req, id):
        c = course_or_404(id)
        rows = a.rows("SELECT * FROM certificates WHERE course = ? AND day = ? ORDER BY name", c["title"], c["day"])
        sheets = "".join(f'<div class="card" style="text-align:center;page-break-after:always"><h2>Certificate of completion</h2><p>{h(organisation)} certifies that</p><h1>{h(r["name"])}</h1><p>completed <b>{h(r["course"])}</b> on {h(r["day"])}</p><p class="muted">Verification code {h(r["code"])}</p></div>' for r in rows if not r["revoked"])
        return a.page("Certificates", sheets or card("None", "<p>No certificates have been issued for this course.</p>"))

    @a.route("/verify", ("GET", "POST"))
    def verify(req):
        result = ""
        if req.method == "POST":
            code = "-".join(core.clean_code(req.text("code"))[i:i + 4] for i in range(0, 12, 4))
            r = a.row("SELECT * FROM certificates WHERE code = ?", code)
            if r is None or not core.verify(secret(), code, r["name"], r["course"], r["day"]):
                result = '<p class="bad">No certificate has this code.</p>'
            elif r["revoked"]:
                result = '<p class="bad">This certificate has been withdrawn.</p>'
            else:
                result = f'<p class="good">Valid: {h(r["name"])} completed {h(r["course"])} on {h(r["day"])}.</p>'
        return a.page("Check a certificate", card("Enter the code", form(a, "/verify", [("code", "Verification code")], "Check") + result))

    return a
