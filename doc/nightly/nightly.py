#! /usr/bin/env python

import cgi
import bottle
import bottle_sqlite
import socket

myname=socket.gethostname()
i_am_local = (myname[-6:] == ".local")
dbfile = "nightly-test.db" if i_am_local else "nightly.db"

plugin = bottle_sqlite.Plugin(dbfile=dbfile)
nightly=bottle.Bottle()
nightly.install(plugin)

urlmap={ 'c': 'C library', 'r': 'R package', 'python': 'Python extension',
         'msvc': 'C library for MSVC' }

def human_size(num):
    num=long(num)
    for x in ['bytes','KB','MB','GB','TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0

bottle.SimpleTemplate.defaults['human_size'] = human_size

# This is the main web page, you can choose your download here
# It can be filtered
@nightly.route("/")
@nightly.route("/list/")
@nightly.route("/list")
@nightly.route("/list/<dtype>")
@nightly.route("/list/<dtype>/<version>")
@nightly.route("/list/<dtype>/<version>/<branch>")
def list_files(db, dtype="all", version="all", branch="all"):

    files = db.execute("SELECT * FROM files    \
                        WHERE type LIKE ? AND version LIKE ? AND branch LIKE ? \
                        ORDER BY version DESC, date DESC",
                       ("%" if dtype=="all" else dtype,
                        "%" if version=="all" else version,
                        "%" if branch=="all" else branch)).fetchall()

    versions=db.execute("SELECT DISTINCT version FROM files \
                         ORDER BY version DESC").fetchall()
    versions=[ e[0] for e in versions ]

    types=db.execute("SELECT DISTINCT type FROM files \
                      ORDER BY type").fetchall()
    types=[ e[0] for e in types ]

    branches=db.execute("SELECT DISTINCT branch FROM files \
                         ORDER BY branch").fetchall()
    branches=[ e[0] for e in branches ]

    # Add test results
    filenames = [ "'" + f['filename'] + "'" for f in files ]
    query = 'SELECT filename, MAX(resultcode) FROM tests \
             WHERE filename IN (%s)            \
             GROUP BY filename, platform, test' % ','.join(filenames)
    tests = dict(db.execute(query).fetchall())

    return bottle.template('main', files=files, versions=versions,
                           types=types, branches=branches, urlmap=urlmap,
                           dtype=dtype, branch=branch, version=version,
                           tests=tests)

@nightly.route("/steal/<filename:path>")
def steal_file(filename):
    return bottle.static_file(filename, "../files", download=True)

@nightly.route("/get/<filename:path>")
def get_file(db, filename):
    db.execute("UPDATE files SET count=count+1 WHERE filename=?", \
               (filename,))
    return steal_file(filename)

@nightly.route("/latest/<dtype>")
@nightly.route("/latest/<dtype>/<branch>")
def get_latest(db, dtype, branch="develop"):

    latest = db.execute("SELECT filename FROM files  \
                         WHERE type=? AND branch=?   \
                         ORDER BY date DESC LIMIT 1",
                        (dtype, branch)).fetchall()
    filename=latest[0][0]

    # Need to redirect here, otherwise "smart" browsers uncompress
    # the .tar.gz file, because the Content-Encoding: gzip header is
    # present.
    bottle.redirect("/steal/" + filename)

@nightly.error(404)
def error404(error):
    return "Page does not exist, maybe your syntax is wrong"

if i_am_local:
    bottle.run(nightly, host="localhost", port=8080, debug=True, 
               reloader=True)
else:
    bottle.run(nightly, server="cgi")