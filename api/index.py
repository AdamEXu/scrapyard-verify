from flask import (
    Flask,
    redirect,
    request,
    session,
    url_for,
    jsonify,
    render_template,
    flash,
)
from urllib.parse import urlencode
import requests
import json
import dotenv
from flask_session import Session
from redis import Redis
import os
import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import random


def send_email(to_email, subject, content):
    message = Mail(
        from_email=("adam@scrapyard.dev", "Adam Xu"),
        to_emails=to_email,
        subject=subject,
        html_content=content,
    )
    try:
        sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e.message)


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

# Configure Redis for session storage
redis_url = os.environ.get("REDIS_URL")
if not redis_url:
    raise ValueError("REDIS_URL environment variable is not set")

try:
    if redis_url.startswith("rediss://"):
        # For SSL connections
        app.config["SESSION_REDIS"] = Redis.from_url(
            redis_url,
            ssl_cert_reqs=None,
            decode_responses=False,  # Changed from True to False
        )
    else:
        # For non-SSL connections
        app.config["SESSION_REDIS"] = Redis.from_url(
            redis_url,
            decode_responses=False,  # Changed from True to False
        )
except Exception as e:
    print(f"Redis connection error: {str(e)}")
    # Fallback to filesystem session
    app.config["SESSION_TYPE"] = "filesystem"
else:
    app.config["SESSION_TYPE"] = "redis"

app.config["SESSION_USE_SIGNER"] = True  # Add this line for signed sessions
Session(app)

dotenv.load_dotenv()

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = "https://verify.scrapyard.dev/discord/callback"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = "https://verify.scrapyard.dev/google/callback"

ATTENDEE_API_URL = os.environ.get("ATTENDEE_API_URL")
API_KEY = os.environ.get("API_KEY")
EVENT_SLUG = os.environ.get("EVENT_SLUG")

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID")
DISCORD_ROLE_ID = os.environ.get("DISCORD_ROLE_ID")


admin_user_ids = [
    "recuH7asdXTb7iKXx",
    "recbqwKQRXSaz292D",
    "recNSBsjyTjM8fuWN",
    "recTF6T0EOwhkG0Tr",
]


@app.route("/")
def index():
    # if user has a session, redirect to /dashboard
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("index.html")


@app.route("/discord")
def discord_verify():
    return render_template("discord-verify.html")


@app.route("/discord/login")
def login_discord():
    discord_auth_url = "https://discord.com/api/oauth2/authorize?" + urlencode(
        {
            "client_id": DISCORD_CLIENT_ID,
            "redirect_uri": DISCORD_REDIRECT_URI,
            "response_type": "code",
            "scope": "identify",
        }
    )
    return redirect(discord_auth_url)


@app.route("/discord/callback")
def discord_callback():
    code = request.args.get("code")
    token_response = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
        },
    ).json()

    user_response = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {token_response['access_token']}"},
    ).json()

    session["discord_id"] = user_response["id"]
    return redirect(url_for("login_google"))


# Google Authentication
@app.route("/google/login")
def login_google():
    google_auth_url = "https://accounts.google.com/o/oauth2/auth?" + urlencode(
        {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "email profile",
        }
    )
    return redirect(google_auth_url)


@app.route("/google/callback")
def google_callback():
    code = request.args.get("code")
    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": GOOGLE_REDIRECT_URI,
        },
    ).json()

    user_response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {token_response['access_token']}"},
    ).json()

    session["email"] = user_response["email"]
    return redirect(url_for("verify_attendee"))


@app.route("/discord/verify")
def verify_attendee():
    if "email" not in session or "discord_id" not in session:
        # return "Missing authentication steps.", 400
        return render_template(
            "fail.html",
            error="Something went wrong. Go back to the homepage and go through the full process again.",
        )

    email = session["email"]
    discord_id = session["discord_id"]

    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}", headers=headers
    ).json()

    attendee = next((a for a in response if a.get("email") == email), None)
    print(response)
    if not attendee:
        return render_template(
            "fail.html",
            error="The provided email is not registered for Scrapyard Silicon Valley.",
        )

    # Check if discord field already exists in organizerNotes
    if "discord" in attendee.get("organizerNotes", {}):
        return render_template(
            "fail.html",
            error="You can only verify one Discord account per signup.",
        )

    # Only send the discord field in the update request
    update_data = {"discord": discord_id}

    update_response = requests.post(
        f"{ATTENDEE_API_URL}/{attendee['id']}/edit?event={EVENT_SLUG}",
        headers=headers,
        json=update_data,
    )

    if update_response.status_code != 200:
        # return "Failed to update attendee.", 500
        return render_template(
            "fail.html",
            error="Something went wrong. Go back to the homepage and go through the full process again.",
        )

    discord_role_response = requests.put(
        f"https://discord.com/api/guilds/{DISCORD_GUILD_ID}/members/{discord_id}/roles/{DISCORD_ROLE_ID}",
        headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
    )

    if discord_role_response.status_code != 204:
        # return "Failed to assign Discord role.", 500
        return render_template(
            "fail.html",
            error="Something went wrong. Go back to the homepage and go through the full process again.",
        )

    # return "Successfully verified and assigned Discord role!"
    return render_template("discord-success.html")


@app.route("/api/refer", methods=["POST"])
def refer():
    data = request.json
    email = data.get("email")
    refer_id = data.get("refer")

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # Fetch all attendees for the event
    response = requests.get(
        "https://scrapyard.hackclub.com/api/organizer/signups?event=siliconvalley",
        headers=headers,
    )

    if response.status_code != 200:
        return "Failed to fetch attendees", 500

    signups = response.json()

    # Check if the user has already signed up with this email
    for signup in signups:
        if signup.get("email", "").lower() == email.lower():
            return "User has already signed up with this email", 400

    # Check if the email is already referred by any other attendee
    for signup in signups:
        organizer_data = signup.get("organizerNotes", {})
        refers = organizer_data.get("refers", [])

        if email in refers:
            return "Email already referred by another attendee", 400

    # Find the intended attendee and add the email to their referral list
    for signup in signups:
        if signup["id"] == refer_id:
            redis_client = app.config["SESSION_REDIS"]

            # Check ALL referral attempts in Redis
            for existing_signup in signups:
                existing_key = f"referral_attempts:{existing_signup['id']}"
                if redis_client.sismember(existing_key, email):
                    return "Email already referred", 400

            organizer_data = signup.get("organizerNotes", {})
            refers = organizer_data.get("refers", [])
            refers.append(email)
            organizer_data["refers"] = refers

            # Send update request
            update_response = requests.post(
                f"https://scrapyard.hackclub.com/api/organizer/signups/{signup['id']}/edit?event=siliconvalley",
                headers=headers,
                json=organizer_data,
            )

            if update_response.status_code == 200:
                # Add to Redis after successful API update
                referral_key = f"referral_attempts:{refer_id}"
                redis_client.sadd(referral_key, email)

                # Rest of the Discord notification code...
                message = f"<@{organizer_data['discord']}> has referred a new person! They now have **{len(refers)}** referrals."
                update_response = requests.post(
                    f"https://discord.com/api/channels/1342398917379358720/messages",
                    headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                    json={"content": message},
                )
                print(update_response.json())
                message = f"{email} has been referred by <@{organizer_data['discord']}> ({signup['fullName']}, {signup['email']}). They now have {len(refers)} referrals. Their referral list is:\n* {'\n* '.join(refers)}"
                update_response = requests.post(
                    f"https://discord.com/api/channels/1337919563358277694/messages",
                    headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                    json={"content": message},
                )
                return "success", 200
            else:
                return "Failed to update referral", 500

    # If we get here, the referrer wasn't found in the API
    # Check Redis before adding
    redis_client = app.config["SESSION_REDIS"]
    referral_key = f"referral_attempts:{refer_id}"
    if redis_client.sismember(referral_key, email):
        return "Email already referred", 400

    # send notification but only the second one
    message = f"{email} signed up with referral code **{refer_id}**. The code now has {len(redis_client.smembers(referral_key)) + 1} uses."
    update_response = requests.post(
        f"https://discord.com/api/channels/1337919563358277694/messages",
        headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
        json={"content": message},
    )

    redis_client.sadd(referral_key, email)
    return "stored", 200


@app.route("/api/refer_info/<refer_id>", methods=["GET"])
def refer_info(refer_id):
    # see if user exists
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    )
    if response.status_code != 200:
        return "Failed to fetch signups", 500

    signups = response.json()
    signup = next((s for s in signups if s["id"] == refer_id), None)
    if not signup:
        redis_client = app.config["SESSION_REDIS"]
        referral_key = f"referral_attempts:{refer_id}"
        referral_attempts = redis_client.smembers(referral_key)
        # Decode bytes to strings
        return jsonify([attempt.decode("utf-8") for attempt in referral_attempts])
    else:
        return jsonify(signup["organizerNotes"].get("refers", []))


@app.route("/auth/google")
def auth_google():
    google_auth_url = "https://accounts.google.com/o/oauth2/auth?" + urlencode(
        {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": "https://id.scrapyard.dev/auth/google/callback",  # Fixed to match intended domain
            "response_type": "code",
            "scope": "email profile",
        }
    )
    return redirect(google_auth_url)


@app.route("/auth/google/callback")
def auth_google_callback():
    try:
        code = request.args.get("code")
        if not code:
            return render_template(
                "fail.html", error="No authentication code received.", link="/"
            )

        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://id.scrapyard.dev/auth/google/callback",  # Fixed to match intended domain
            },
        ).json()

        if "error" in token_response or "access_token" not in token_response:
            return render_template(
                "fail.html", error="Failed to authenticate with Google.", link="/"
            )

        user_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_response['access_token']}"},
        ).json()

        if "error" in user_response or "email" not in user_response:
            return render_template(
                "fail.html",
                error="Failed to get user information from Google.",
                link="/auth/google",
            )

        session["email"] = user_response["email"]

        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(
            f"{ATTENDEE_API_URL}?event={EVENT_SLUG}", headers=headers
        ).json()

        attendee = next(
            (a for a in response if a.get("email").lower() == session["email"].lower()),
            None,
        )
        if not attendee:
            return render_template(
                "fail.html",
                error="The provided email is not registered for Scrapyard Silicon Valley.",
                link="/login",
            )

        session["user_id"] = attendee["id"]
        return redirect("/")

    except Exception as e:
        return render_template(
            "fail.html",
            error="An unexpected error occurred during authentication.",
            link="/auth/google",
        )
    # return "success"


admin_nav = """
<a href="/admin" class="nav-link">Admin</a>
"""


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    if session["user_id"] in admin_user_ids:
        return render_template("dashboard.html", admin_nav=admin_nav)
    return render_template("dashboard.html")


panels = ["dashboard", "meal-form", "polls"]
admin_panels = []


@app.route("/dashboard/<panel_id>")
def dashboard_panel(panel_id):
    if "user_id" not in session:
        return redirect("/")
    if panel_id not in panels:
        return redirect("/dashboard")
    if session["user_id"] in admin_user_ids:
        return render_template("dashboard.html", admin_nav=admin_nav, panel_id=panel_id)
    return render_template("dashboard.html", panel_id=panel_id)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/login")
def login():
    return redirect("/auth/google")


@app.route("/admin")
def admin():
    if "user_id" not in session:
        return redirect("/")
    if session["user_id"] not in admin_user_ids:
        return redirect("/")
    return render_template("admin.html")


@app.route("/admin/meal-grabber")
def meal_grabber():
    if "user_id" not in session:
        return redirect("/")
    if session["user_id"] not in admin_user_ids:
        return redirect("/")
    return render_template("meal-grabber.html")


@app.route("/api/list_referrals")
def list_referrals():
    if "user_id" not in session:
        return redirect("/")
    if session["user_id"] not in admin_user_ids:
        return redirect("/")
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    )
    if response.status_code != 200:
        return "Failed to fetch signups", 500

    refers = {}
    for signup in response.json():
        organizer_data = signup.get("organizerNotes", {})
        # refers[signup["id"]] = organizer_data.get("refers", [])
        if "refers" in organizer_data:
            refers[signup["id"]] = {"refers": organizer_data["refers"], "signed_up": {}}
            # go through each email and check if they are signed up
            for email in organizer_data["refers"]:
                # if signed up, signedup = true
                if any(s["email"] == email for s in response.json()):
                    refers[signup["id"]]["signed_up"]["email"] = True
                else:
                    refers[signup["id"]]["signed_up"]["email"] = False

    # Decode Redis bytes data
    redis_client = app.config["SESSION_REDIS"]
    for key in redis_client.keys("referral_attempts:*"):
        signup_id = key.decode("utf-8").split(":")[1]
        # Decode each byte string in the set to UTF-8
        refers[signup_id] = {
            "refers": [
                attempt.decode("utf-8") for attempt in redis_client.smembers(key)
            ],
            "signed_up": {},
        }
        for email in refers[signup_id]["refers"]:
            if any(s["email"] == email for s in response.json()):
                refers[signup_id]["signed_up"]["email"] = True
            else:
                refers[signup_id]["signed_up"]["email"] = False

    return jsonify(refers)


@app.route("/api/remove_referral", methods=["POST"])
def remove_referral():
    if "user_id" not in session:
        return redirect("/")
    if session["user_id"] not in admin_user_ids:
        return redirect("/")

    data = request.json
    signup_id = data.get("signup_id")
    email = data.get("email")

    if not signup_id or not email:
        return jsonify({"error": "Missing signup_id or email"}), 400
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    ).json()
    signup = next((s for s in response if s["id"] == signup_id), None)
    if not signup:
        # its redis time
        redis_client = app.config["SESSION_REDIS"]
        referral_key = f"referral_attempts:{signup_id}"
        redis_client.srem(referral_key, email)
        if redis_client.scard(referral_key) == 0:
            redis_client.delete(referral_key)
        return "removed", 200
    else:
        organizer_notes = signup.get("organizerNotes", {})
        if "refers" in organizer_notes:
            organizer_notes["refers"] = [
                r for r in organizer_notes["refers"] if r != email
            ]
            update_response = requests.post(
                f"{ATTENDEE_API_URL}/{signup['id']}/edit?event={EVENT_SLUG}",
                headers=headers,
                json=organizer_notes,
            )
            if update_response.status_code == 200:
                return "removed", 200
            else:
                return (
                    jsonify(
                        {
                            "error": "Failed to update attendee",
                            "details": update_response.text,
                        }
                    ),
                    500,
                )
        else:
            return "removed", 200


@app.route("/api/user_info", methods=["POST"])
def user_info():
    if "user_id" in session:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        try:
            response = requests.get(
                f"{ATTENDEE_API_URL}?event={EVENT_SLUG}", headers=headers
            ).json()
            user_id = session["user_id"]
            attendee = next((a for a in response if a.get("id") == user_id), None)
            return jsonify(attendee or {})
        except Exception as e:
            return (
                jsonify({"error": "Failed to fetch attendee data", "details": str(e)}),
                500,
            )
    return jsonify({"error": "Unauthorized"}), 401


@app.route("/api/admin-set-meal-form", methods=["POST"])
def admin_set_meal_form():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    if session["user_id"] not in admin_user_ids:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    attendee_id = data.get("attendee_id")
    meal_form = data.get("meal_form")

    if not attendee_id or not meal_form:
        return jsonify({"error": "Missing attendee_id or meal_form"}), 400

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # Get attendee data
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    ).json()

    attendee = next((a for a in response if a.get("id") == attendee_id), None)
    if not attendee:
        return jsonify({"error": "Attendee not found"}), 404

    # Update organizer notes with meal form data
    organizer_notes = attendee.get("organizerNotes", {})
    organizer_notes["mealForm"] = meal_form

    # Save back to API
    update_response = requests.post(
        f"{ATTENDEE_API_URL}/{attendee_id}/edit?event={EVENT_SLUG}",
        headers=headers,
        json=organizer_notes,
    )

    if update_response.status_code == 200:
        return jsonify(
            {
                "success": True,
                "message": f"Successfully updated meal form for {attendee.get('preferredName') or attendee.get('fullName')}",
            }
        )
    else:
        return (
            jsonify(
                {
                    "error": "Failed to update meal form",
                    "details": update_response.text,
                }
            ),
            500,
        )


@app.route("/api/get-attendees")
def get_attendees():
    if not "user_id" in session:
        return redirect("/")
    if session["user_id"] not in admin_user_ids:
        return redirect("/")
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    )
    if response.status_code != 200:
        return "Failed to fetch signups", 500

    # Get all attendees
    attendees = response.json()

    # Remove duplicates, keeping the first instance of each attendee
    # Use a dictionary to track seen emails (case-insensitive)
    seen_emails = {}
    unique_attendees = []

    for attendee in attendees:
        email = attendee.get("email", "").lower()
        if email and email not in seen_emails:
            seen_emails[email] = True
            unique_attendees.append(attendee)

    return jsonify(unique_attendees)


@app.route("/api/track-meal-pickup", methods=["POST"])
def track_meal_pickup():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    if session["user_id"] not in admin_user_ids:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    attendee_id = data.get("attendee_id")
    meal_type = data.get("meal_type")
    pickup_status = data.get("pickup_status", True)  # Default to True (picked up)

    if not attendee_id or not meal_type:
        return jsonify({"error": "Missing required fields"}), 400

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # Get attendee data
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    ).json()

    attendee = next((a for a in response if str(a.get("id")) == str(attendee_id)), None)
    if not attendee:
        return jsonify({"error": "Attendee not found"}), 404

    # Update organizer notes with meal pickup status
    organizer_notes = attendee.get("organizerNotes", {})
    if not organizer_notes:
        organizer_notes = {}

    meal_pickups = organizer_notes.get("mealPickups", {})
    if not meal_pickups:
        meal_pickups = {}

    # Update the pickup status for the specified meal
    if pickup_status:
        meal_pickups[meal_type] = True
    else:
        # If we're marking as not picked up, set to False
        meal_pickups[meal_type] = False

    organizer_notes["mealPickups"] = meal_pickups

    # Update the attendee record - use the same method as other endpoints
    update_response = requests.post(
        f"{ATTENDEE_API_URL}/{attendee_id}/edit?event={EVENT_SLUG}",
        headers=headers,
        json=organizer_notes,
    )

    if update_response.status_code != 200:
        return (
            jsonify(
                {
                    "error": "Failed to update meal pickup status",
                    "details": update_response.text,
                }
            ),
            500,
        )

    # Return success response with attendee name for the toast notification
    return jsonify(
        {
            "success": True,
            "attendee": attendee.get("preferredName")
            or attendee.get("fullName")
            or "Attendee",
            "meal_type": meal_type,
            "picked_up": pickup_status,
        }
    )


# Waitlist-related API endpoints
@app.route("/api/approve", methods=["POST"])
def approve():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    if session["user_id"] not in admin_user_ids:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    attendee_id = data.get("attendee_id")
    resend = data.get("resend", False)

    if not attendee_id:
        return jsonify({"error": "Missing attendee_id"}), 400

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # Get attendee data
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    ).json()

    attendee = next((a for a in response if a.get("id") == attendee_id), None)
    if not attendee:
        return jsonify({"error": "Attendee not found"}), 404

    # If this is not just a resend request, update the status
    if not resend:
        # Update organizer notes with waitlist status
        organizer_notes = attendee.get("organizerNotes", {})
        organizer_notes["waitlist"] = "approved"

        # Save back to API
        update_response = requests.post(
            f"{ATTENDEE_API_URL}/{attendee['id']}/edit?event={EVENT_SLUG}",
            headers=headers,
            json=organizer_notes,
        )

        if update_response.status_code != 200:
            return (
                jsonify(
                    {
                        "error": "Failed to update waitlist status",
                        "details": update_response.text,
                    }
                ),
                500,
            )

    # Send approval email (for both new approvals and resends)
    try:
        send_email(
            attendee["email"],
            "[Important] Scrapyard Silicon Valley Info",
            render_template("emails/approval_email.html", attendee=attendee),
        )
    except Exception as e:
        print(f"Failed to send approval email: {e}")
        if resend:
            return (
                jsonify(
                    {
                        "error": "Failed to send email",
                        "details": str(e),
                    }
                ),
                500,
            )

    return jsonify(
        {
            "success": True,
            "attendee": attendee["preferredName"] or attendee["fullName"],
        }
    )


@app.route("/api/send-to-all", methods=["POST"])
def send_to_all():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    if session["user_id"] not in admin_user_ids:
        return jsonify({"error": "Unauthorized"}), 403

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # Get all attendees
    response = requests.get(
        f"{ATTENDEE_API_URL}?event={EVENT_SLUG}",
        headers=headers,
    ).json()

    # Filter for waitlisted attendees (those who never received the info)
    waitlisted_attendees = [
        a
        for a in response
        if a.get("organizerNotes", {}).get("waitlist") == "waitlisted"
    ]

    success_count = 0
    failed_emails = []

    # Send emails and update status to approved
    for attendee in waitlisted_attendees:
        try:
            # Update status to approved
            organizer_notes = attendee.get("organizerNotes", {})
            organizer_notes["waitlist"] = "approved"

            # Save back to API
            update_response = requests.post(
                f"{ATTENDEE_API_URL}/{attendee['id']}/edit?event={EVENT_SLUG}",
                headers=headers,
                json=organizer_notes,
            )

            if update_response.status_code != 200:
                print(f"Failed to update status for {attendee['email']}")
                failed_emails.append(attendee["email"])
                continue

            # Send approval email
            send_email(
                attendee["email"],
                "[Important] Scrapyard Silicon Valley Info",
                render_template("emails/approval_email.html", attendee=attendee),
            )
            success_count += 1
        except Exception as e:
            print(f"Failed to process {attendee['email']}: {e}")
            failed_emails.append(attendee["email"])

    return jsonify(
        {
            "success": True,
            "total": len(waitlisted_attendees),
            "sent": success_count,
            "failed": failed_emails,
        }
    )


# @app.route("/test-success")
# def test_success():
#     return render_template("success.html")


# 404
@app.errorhandler(404)
def page_not_found(e):
    return redirect("/", code=302)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
