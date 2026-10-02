import json
import logging
import os
import tempfile
from datetime import datetime, timedelta

import google.generativeai as AI
import requests
import speech_recognition as sr
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from dotenv import load_dotenv
from pydub import AudioSegment

from SmartGoAI import settings
from .models import Plans, Reminder, Task, USER


logger = logging.getLogger(__name__)

load_dotenv()


# -------------------------------------------------------------------
# Gemini AI
# -------------------------------------------------------------------

AI.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

AI_MODEL = AI.GenerativeModel("gemini-3.6-flash")


# -------------------------------------------------------------------
# FFmpeg configuration
#
# Put these in your .env file:
#
# FFMPEG_PATH=C:\path\to\ffmpeg.exe
# FFPROBE_PATH=C:\path\to\ffprobe.exe
#
# If FFmpeg is already available in PATH, pydub can use it directly.
# -------------------------------------------------------------------

FFMPEG_PATH = os.getenv("FFMPEG_PATH")
FFPROBE_PATH = os.getenv("FFPROBE_PATH")

if FFMPEG_PATH and os.path.isfile(FFMPEG_PATH):
    AudioSegment.converter = FFMPEG_PATH

if FFPROBE_PATH and os.path.isfile(FFPROBE_PATH):
    AudioSegment.ffprobe = FFPROBE_PATH


# -------------------------------------------------------------------
# Authentication / pages
# -------------------------------------------------------------------

def signup(request):
    return render(request, "signup.html")


def signup_post(request):
    if request.method != "POST":
        return redirect("/myapp/signup/")

    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    age = request.POST.get("age", "").strip()
    place = request.POST.get("place", "").strip()
    photo = request.FILES.get("photo")
    password = request.POST.get("password", "")

    if not phone or not password:
        messages.error(request, "Phone number and password are required.")
        return redirect("/myapp/signup/")

    if User.objects.filter(username=phone).exists():
        messages.error(request, "An account with this phone number already exists.")
        return redirect("/myapp/signup/")

    try:
        user = User.objects.create_user(
            username=phone,
            password=password,
        )

        USER.objects.create(
            name=name,
            phone=phone,
            age=age,
            place=place,
            photo=photo,
            LOGIN=user,
        )

        messages.success(request, "Account created successfully!")
        return redirect("/myapp/login/")

    except Exception:
        logger.exception("Signup failed.")
        messages.error(request, "Unable to create the account. Please try again.")
        return redirect("/myapp/signup/")


@login_required
def logout_post(request):
    if request.method == "POST":
        logout(request)

    return redirect("/myapp/login/")


def login_page(request):
    return render(request, "login.html")


def login_post(request):
    if request.method != "POST":
        return redirect("/myapp/login/")

    phone = request.POST.get("phone", "").strip()
    password = request.POST.get("password", "")

    user = authenticate(
        request,
        username=phone,
        password=password,
    )

    if user is not None:
        login(request, user)
        return redirect("/myapp/home/")

    messages.error(request, "Invalid phone number or password.")
    return redirect("/myapp/login/")


@login_required
def homepage(request):
    return render(request, "homepage.html")


# -------------------------------------------------------------------
# Voice input
# -------------------------------------------------------------------

def voice_to_text(audio_file):
    recognizer = sr.Recognizer()

    # Unique temporary filenames avoid collisions between requests.
    temp_id = next(tempfile._get_candidate_names())

    webm_path = os.path.join(
        tempfile.gettempdir(),
        f"smartgo_audio_{temp_id}.webm",
    )

    wav_path = os.path.join(
        tempfile.gettempdir(),
        f"smartgo_audio_{temp_id}.wav",
    )

    try:
        with open(webm_path, "wb") as destination:
            for chunk in audio_file.chunks():
                destination.write(chunk)

        converted_audio = AudioSegment.from_file(
            webm_path,
            format="webm",
        )

        converted_audio.export(
            wav_path,
            format="wav",
        )

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        return recognizer.recognize_google(audio_data)

    except sr.UnknownValueError:
        logger.warning("Speech could not be understood.")
        return ""

    except sr.RequestError:
        logger.exception("Google Speech Recognition request failed.")
        return ""

    except Exception:
        logger.exception("Voice processing failed.")
        return ""

    finally:
        for file_path in (webm_path, wav_path):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                logger.warning("Could not remove temporary file: %s", file_path)


# -------------------------------------------------------------------
# Weather
# -------------------------------------------------------------------

def get_weather(destination, plan_date):
    weather_result = {
        "condition": None,
        "temperature": None,
        "rain_expected": False,
        "weather_advice": None,
    }

    try:
        api_key = getattr(
            settings,
            "OPENWEATHER_API_KEY",
            None,
        )

        if not api_key:
            logger.warning("OPENWEATHER_API_KEY is missing.")
            return weather_result

        target_date = (
            plan_date
            if hasattr(plan_date, "year")
            else datetime.strptime(str(plan_date), "%Y-%m-%d").date()
        )

        response = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                "q": destination,
                "appid": api_key,
                "units": "metric",
            },
            timeout=10,
        )

        if response.status_code != 200:
            logger.warning(
                "Weather API returned status %s: %s",
                response.status_code,
                response.text,
            )
            return weather_result

        weather_data = response.json()
        forecasts = weather_data.get("list", [])

        date_forecasts = []

        for forecast in forecasts:
            forecast_datetime = datetime.strptime(
                forecast["dt_txt"],
                "%Y-%m-%d %H:%M:%S",
            )

            if forecast_datetime.date() == target_date:
                date_forecasts.append(forecast)

        if not date_forecasts:
            weather_result["weather_advice"] = (
                "Weather forecast is not available for this date."
            )
            return weather_result

        temperatures = []
        conditions = []
        rain_found = False

        for forecast in date_forecasts:
            temperature = forecast.get("main", {}).get("temp")

            if temperature is not None:
                temperatures.append(temperature)

            weather_list = forecast.get("weather", [])

            if weather_list:
                weather_item = weather_list[0]

                description = weather_item.get(
                    "description",
                    "",
                ).lower()

                main_condition = weather_item.get(
                    "main",
                    "",
                ).lower()

                if description:
                    conditions.append(description)

                if main_condition in {"rain", "drizzle"}:
                    rain_found = True

            if forecast.get("rain"):
                rain_found = True

        average_temperature = (
            round(sum(temperatures) / len(temperatures), 1)
            if temperatures
            else None
        )

        condition = (
            max(set(conditions), key=conditions.count)
            if conditions
            else None
        )

        if rain_found:
            weather_advice = (
                "Rain may occur. Carry an umbrella or raincoat "
                "and protect important documents."
            )
        elif average_temperature is not None and average_temperature >= 35:
            weather_advice = (
                "High temperature expected. Carry water, sunglasses "
                "and stay hydrated."
            )
        elif average_temperature is not None and average_temperature <= 15:
            weather_advice = (
                "Cool weather expected. Consider carrying warm clothing."
            )
        else:
            weather_advice = (
                "Weather conditions look comfortable for the planned activity."
            )

        return {
            "condition": condition,
            "temperature": average_temperature,
            "rain_expected": rain_found,
            "weather_advice": weather_advice,
        }

    except Exception:
        logger.exception("Weather lookup failed.")
        return weather_result


# -------------------------------------------------------------------
# AI helpers
# -------------------------------------------------------------------

def clean_ai_json(response_text):
    """Remove optional Markdown code fences before JSON parsing."""
    response_text = (response_text or "").strip()

    if response_text.startswith("```"):
        lines = response_text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        response_text = "\n".join(lines).strip()

    return response_text


def generate_json_response(prompt):
    """Generate an AI response and return it as Python data."""
    response = AI_MODEL.generate_content(prompt)
    response_text = clean_ai_json(response.text)

    return json.loads(response_text)


# -------------------------------------------------------------------
# Plan analyser
# -------------------------------------------------------------------

@login_required
def Analyser(request):
    if request.method != "POST":
        return render(request, "homepage.html")

    user_input = request.POST.get("input", "").strip()
    audio_file = request.FILES.get("audio")

    if not user_input and audio_file:
        user_input = voice_to_text(audio_file)

        if not user_input:
            messages.error(
                request,
                "Unable to understand the voice input.",
            )
            return redirect("/myapp/home/")

    if not user_input:
        messages.warning(request, "Please enter something.")
        return redirect("/myapp/home/")

    try:
        current_datetime = timezone.localtime()
        current_date = current_datetime.date()
        current_time = current_datetime.time()

        extraction_prompt = f"""
You are SmartGo AI, an intelligent context-aware personal planning assistant.

Analyze the user's request and extract the following information.

USER REQUEST:
{user_input}

CURRENT DATE:
{current_date}

CURRENT TIME:
{current_time}

Return ONLY valid JSON in exactly this format:

{{
    "title": "",
    "description": "",
    "date": "",
    "time": "",
    "destination": "",
    "event_type": ""
}}

Rules:

1. Convert relative dates such as today, tomorrow, next Monday, etc. into YYYY-MM-DD.
2. Convert time into 24-hour HH:MM format.
3. If the user gives an event time such as 2 PM, store it as 14:00.
4. If no date is given, return an empty string.
5. If no time is available, return an empty string.
6. If destination is not mentioned, return an empty string.
7. Do not add explanations outside the JSON.
"""

        extracted_data = generate_json_response(extraction_prompt)

        title = str(extracted_data.get("title", "")).strip()
        description = str(extracted_data.get("description", "")).strip()
        date_string = str(extracted_data.get("date", "")).strip()
        time_string = str(extracted_data.get("time", "")).strip()
        destination = str(extracted_data.get("destination", "")).strip()
        event_type = str(extracted_data.get("event_type", "")).strip()

        plan_date = None
        plan_time = None

        if date_string:
            plan_date = datetime.strptime(
                date_string,
                "%Y-%m-%d",
            ).date()

        if time_string:
            plan_time = datetime.strptime(
                time_string,
                "%H:%M",
            ).time()

        weather_condition = ""
        temperature = ""
        rain_expected = False
        weather_advice = ""

        if destination and plan_date:
            weather = get_weather(destination, plan_date)

            # Important: get_weather() returns "condition",
            # not "weather_condition".
            weather_condition = weather.get("condition") or ""
            temperature = str(weather.get("temperature") or "")
            rain_expected = bool(weather.get("rain_expected", False))
            weather_advice = weather.get("weather_advice") or ""

        final_prompt = f"""
You are SmartGo AI.

Create a practical plan for the following user request.

USER REQUEST:
{user_input}

PLAN DETAILS:

Title:
{title}

Description:
{description}

Date:
{plan_date}

Time:
{plan_time}

Destination:
{destination}

Event Type:
{event_type}

Generate practical tasks that the user should complete before or for this event.

Return ONLY valid JSON in this format:

{{
    "tasks": [
        "task 1",
        "task 2",
        "task 3",
        "task 4",
        "task 5"
    ]
}}

Rules:

1. Generate between 2 and 5 useful tasks.
2. Tasks must be specific to the user's event.
3. Do not generate reminders.
4. Do not include explanations outside JSON.
"""

        final_data = generate_json_response(final_prompt)
        tasks = final_data.get("tasks", [])

        if not isinstance(tasks, list):
            raise ValueError("AI returned an invalid tasks format.")

        current_user = USER.objects.get(LOGIN=request.user)

        print("USER FOUND:", current_user)

        plan = Plans.objects.create(
            USER=current_user,
            title=title or "Untitled Plan",
            description=description or "No description",
            date=plan_date,
            time=plan_time,
            status="pending",
            destination=destination or "",
            event_type=event_type or "",
            weather_condition=weather_condition or "",
            temperature=temperature or "",
            rain_expected=bool(rain_expected),
            weather_advice=weather_advice or "",
        )

        print("PLAN CREATED:", plan.id)

        for task_text in tasks[:5]:
            task_text = str(task_text).strip()

            if task_text:
                Task.objects.create(
    PLANS=plan,
    task=task_text,
    completed="pending",
)

        if plan_date and plan_time:
            event_datetime = timezone.make_aware(
                datetime.combine(plan_date, plan_time)
            )

            reminder_offsets = [
                (timedelta(hours=1), "1 hour"),
                (timedelta(minutes=30), "30 minutes"),
                (timedelta(minutes=10), "10 minutes"),
            ]

            for offset, label in reminder_offsets:
                reminder_time = event_datetime - offset

                if reminder_time <= current_datetime:
                    continue

                if label == "1 hour":
                    message = f"{title} is in 1 hour."
                elif label == "30 minutes":
                    message = f"{title} is in 30 minutes."
                else:
                    message = f"{title} starts in 10 minutes."

                Reminder.objects.create(
    PLANS=plan,
    message=message,
    reminder_time=reminder_time,
    completed="pending",
    notified=False,
)

        messages.success(
            request,
            "Your plan and reminders were created successfully.",
        )

    except json.JSONDecodeError:
        messages.error(
            request,
            "AI returned an invalid response. Please try again.",
        )

    except (ValueError, TypeError):
        logger.exception("Invalid AI plan data.")
        messages.error(
            request,
            "The AI returned invalid plan data. Please try again.",
        )

    except USER.DoesNotExist:
        messages.error(
            request,
            "User profile not found.",
        )

    except Exception:
        logger.exception("Plan analysis failed.")
        messages.error(
            request,
            "Something went wrong while creating your plan.",
        )

    return redirect("/myapp/home/")


# -------------------------------------------------------------------
# Plans
# -------------------------------------------------------------------

@login_required
def plans(request):
    user_plans = Plans.objects.filter(
        USER__LOGIN=request.user
    ).order_by("-id")

    return render(
        request,
        "plans.html",
        {"plans": user_plans},
    )


# -------------------------------------------------------------------
# Tasks
# -------------------------------------------------------------------

@login_required
def complete_task(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid request method.",
            },
            status=405,
        )

    try:
        data = json.loads(request.body)
        task_id = data.get("task_id")
        completed = data.get("completed")

        if task_id is None:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Task ID is required.",
                },
                status=400,
            )

        task = Task.objects.get(
            id=task_id,
            PLANS__USER__LOGIN=request.user,
        )

        task.completed = bool(completed)
        task.save(update_fields=["completed"])

        return JsonResponse({"status": "success"})

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON.",
            },
            status=400,
        )

    except Task.DoesNotExist:
        return JsonResponse(
            {
                "status": "error",
                "message": "Task not found.",
            },
            status=404,
        )

    except Exception:
        logger.exception("Could not update task.")
        return JsonResponse(
            {
                "status": "error",
                "message": "Could not update task.",
            },
            status=500,
        )


# -------------------------------------------------------------------
# History
# -------------------------------------------------------------------

@login_required
def view_history(request):
    today = timezone.localdate()

    user_plans = Plans.objects.filter(
        USER__LOGIN=request.user,
        date__lt=today,
    ).order_by("-date")

    return render(
        request,
        "history.html",
        {"data": user_plans},
    )


# -------------------------------------------------------------------
# Reminders
# -------------------------------------------------------------------

@login_required
def complete_reminder(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid request method.",
            },
            status=405,
        )

    try:
        data = json.loads(request.body)

        reminder_id = data.get("reminder_id")
        completed = data.get("completed")

        if reminder_id is None:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Reminder ID is required.",
                },
                status=400,
            )

        # Important: verify that the reminder belongs
        # to the logged-in user.
        reminder = Reminder.objects.get(
            id=reminder_id,
            PLANS__USER__LOGIN=request.user,
        )

        reminder.completed = bool(completed)
        reminder.save(update_fields=["completed"])

        return JsonResponse({"status": "success"})

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON.",
            },
            status=400,
        )

    except Reminder.DoesNotExist:
        return JsonResponse(
            {
                "status": "error",
                "message": "Reminder not found.",
            },
            status=404,
        )

    except Exception:
        logger.exception("Could not update reminder.")
        return JsonResponse(
            {
                "status": "error",
                "message": "Could not update reminder.",
            },
            status=500,
        )


# -------------------------------------------------------------------
# Reminder notification worker
#
# IMPORTANT:
# This function is kept here for your existing Windows desktop
# notification system, but the thread should ideally be started from
# a dedicated Django management command instead of at module import.
# -------------------------------------------------------------------

def reminder_thread():
    try:
        from winotify import Notification, audio
    except ImportError:
        logger.exception("winotify is not installed.")
        return

    while True:
        try:
            now = timezone.localtime()

            reminders = Reminder.objects.filter(
                reminder_time__lte=now,
                notified=False,
            )

            for reminder in reminders:
                toast = Notification(
                    app_id="SmartGo AI",
                    title="SmartGo Reminder",
                    msg=reminder.message,
                    duration="long",
                )

                toast.set_audio(audio.Default, loop=False)
                toast.show()

                reminder.notified = True
                reminder.save(update_fields=["notified"])

        except Exception:
            logger.exception("Reminder thread failed.")

        # Check every 10 seconds.
        import time
        time.sleep(10)
