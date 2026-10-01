
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from SmartGoAI import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from datetime import datetime, timedelta

import tempfile
import os
import json
import requests

from datetime import datetime

import google.generativeai as AI
import speech_recognition as sr

from pydub import AudioSegment

from myapp.models import *


import threading
import time
from datetime import datetime
from winotify import Notification, audio
from .models import Reminder

from dotenv import load_dotenv

load_dotenv()

AI.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

AI_MODEL = AI.GenerativeModel(
    "gemini-3.6-flash"
)

FFMPEG_PATH = r"C:\Users\rahul\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"

FFPROBE_PATH = r"C:\Users\rahul\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"


FFMPEG_BIN = os.path.dirname(
    FFMPEG_PATH
)

os.environ["PATH"] = (
    FFMPEG_BIN
    + os.pathsep
    + os.environ.get("PATH", "")
)

AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffmpeg = FFMPEG_PATH
AudioSegment.ffprobe = FFPROBE_PATH


print(
    "FFmpeg exists:",
    os.path.isfile(FFMPEG_PATH)
)

print(
    "FFprobe exists:",
    os.path.isfile(FFPROBE_PATH)
)

print(
    "FFmpeg:",
    AudioSegment.converter
)

print(
    "FFprobe:",
    AudioSegment.ffprobe
)


def signup(request):
    return render(request,'signup.html')

def logout_post(request):
    logout(request)
    return redirect('/myapp/login/')

def signup_post(request):

    name = request.POST.get('name')
    phone = request.POST.get('phone')
    age = request.POST.get('age')
    place = request.POST.get('place')
    photo = request.FILES.get('photo')
    password = request.POST.get('password')

    user = User.objects.create_user(
        username=phone,
        password=password
    )

    USER.objects.create(
        name=name,
        phone=phone,
        age=age,
        place=place,
        photo=photo,
        LOGIN=user
    )

    messages.warning(
        request,
        "Account created successfully!"
    )

    return redirect(
        '/myapp/login/'
    )


def login_page(request):

    return render(
        request,
        'login.html'
    )


def login_post(request):

    phone = request.POST.get('phone')
    password = request.POST.get('password')

    user = authenticate(
        request,
        username=phone,
        password=password
    )

    if user is not None:

        login(
            request,
            user
        )

        return redirect(
            '/myapp/home/'
        )

    else:

        messages.error(
            request,
            "Invalid phone number or password."
        )

        return redirect(
            '/myapp/login/'
        )


@login_required
def homepage(request):

    return render(
        request,
        'homepage.html'
    )


def voice_to_text(audio_file):

    recognizer = sr.Recognizer()

    webm_path = os.path.join(
        tempfile.gettempdir(),
        "smartgo_audio.webm"
    )

    wav_path = os.path.join(
        tempfile.gettempdir(),
        "smartgo_audio.wav"
    )

    try:

        with open(
            webm_path,
            "wb+"
        ) as destination:

            for chunk in audio_file.chunks():

                destination.write(
                    chunk
                )

        print(
            "Audio saved:",
            webm_path
        )

        audio = AudioSegment.from_file(
            webm_path,
            format="webm"
        )

        audio.export(
            wav_path,
            format="wav"
        )

        print(
            "WAV created:",
            wav_path
        )

        with sr.AudioFile(
            wav_path
        ) as source:

            audio_data = recognizer.record(
                source
            )

        user_audio = recognizer.recognize_google(
            audio_data
        )

        print(
            "User said:",
            user_audio
        )

        return user_audio

    except sr.UnknownValueError:

        print(
            "Could not understand audio"
        )

        return ""

    except sr.RequestError as e:

        print(
            "Google Speech Recognition error:",
            e
        )

        return ""

    except Exception as e:

        print(
            "Voice error:",
            repr(e)
        )

        return ""

    finally:

        if os.path.exists(
            webm_path
        ):

            os.remove(
                webm_path
            )

        if os.path.exists(
            wav_path
        ):

            os.remove(
                wav_path
            )


def get_weather(
    destination,
    plan_date
):

    weather_result = {

        "condition": None,

        "temperature": None,

        "rain_expected": False,

        "weather_advice": None

    }

    try:

        api_key = getattr(
            settings,
            "OPENWEATHER_API_KEY",
            None
        )

        if not api_key:

            print(
                "OPENWEATHER_API_KEY is missing."
            )

            return weather_result

        target_date = datetime.strptime(
            str(plan_date),
            "%Y-%m-%d"
        ).date()

        url = (
            "https://api.openweathermap.org/"
            "data/2.5/forecast"
        )

        params = {

            "q": destination,

            "appid": api_key,

            "units": "metric"

        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        print(
            "Weather API status:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "Weather API error:",
                response.text
            )

            return weather_result

        weather_data = response.json()

        forecasts = weather_data.get(
            "list",
            []
        )

        if not forecasts:

            print(
                "No forecast data found."
            )

            return weather_result

        date_forecasts = []

        for forecast in forecasts:

            forecast_datetime = datetime.strptime(
                forecast["dt_txt"],
                "%Y-%m-%d %H:%M:%S"
            )

            forecast_date = (
                forecast_datetime.date()
            )

            if forecast_date == target_date:

                date_forecasts.append(
                    forecast
                )

        if not date_forecasts:

            print(
                "No weather forecast available for:",
                target_date
            )

            weather_result[
                "weather_advice"
            ] = (
                "Weather forecast is not "
                "available for this date."
            )

            return weather_result

        temperatures = []

        conditions = []

        rain_found = False

        for forecast in date_forecasts:

            temperature = (
                forecast
                .get("main", {})
                .get("temp")
            )

            if temperature is not None:

                temperatures.append(
                    temperature
                )

            weather_list = forecast.get(
                "weather",
                []
            )

            if weather_list:

                condition = (
                    weather_list[0]
                    .get(
                        "description",
                        ""
                    )
                    .lower()
                )

                conditions.append(
                    condition
                )

                main_condition = (
                    weather_list[0]
                    .get(
                        "main",
                        ""
                    )
                    .lower()
                )

                if (
                    "rain" in main_condition
                    or
                    "drizzle" in main_condition
                ):

                    rain_found = True

            if "rain" in forecast:

                rain_found = True

        if temperatures:

            average_temperature = round(
                sum(temperatures)
                / len(temperatures),
                1
            )

        else:

            average_temperature = None

        if conditions:

            condition = max(
                set(conditions),
                key=conditions.count
            )

        else:

            condition = None

        if rain_found:

            weather_advice = (
                "Rain may occur. "
                "Carry an umbrella or raincoat "
                "and protect important documents."
            )

        elif (
            average_temperature is not None
            and average_temperature >= 35
        ):

            weather_advice = (
                "High temperature expected. "
                "Carry water, sunglasses "
                "and stay hydrated."
            )

        elif (
            average_temperature is not None
            and average_temperature <= 15
        ):

            weather_advice = (
                "Cool weather expected. "
                "Consider carrying warm clothing."
            )

        else:

            weather_advice = (
                "Weather conditions look "
                "comfortable for the planned activity."
            )

        weather_result = {

            "condition": condition,

            "temperature": average_temperature,

            "rain_expected": rain_found,

            "weather_advice": weather_advice

        }

        print(
            "WEATHER RESULT:",
            weather_result
        )

        return weather_result

    except Exception as e:

        print(
            "GET WEATHER ERROR:",
            repr(e)
        )

        return weather_result


@login_required

def Analyser(request):

    if request.method != "POST":
        return render(request, "homepage.html")

    user_input = request.POST.get("input", "").strip()
    audio_file = request.FILES.get("audio")

    if not user_input and audio_file:
        try:
            user_input = voice_to_text(audio_file)
        except Exception:
            messages.error(request, "Unable to process the audio.")
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
4. If no date is given but the user says "today", use the current date.
5. If no time is available, return an empty string.
6. If destination is not mentioned, return an empty string.
7. Do not add explanations outside the JSON.
"""

        response = AI_MODEL.generate_content(extraction_prompt)

        response_text = response.text.strip()

        if response_text.startswith("```"):
            response_text = response_text.replace("```json", "")
            response_text = response_text.replace("```", "")
            response_text = response_text.strip()

        extracted_data = json.loads(response_text)

        title = extracted_data.get("title", "").strip()
        description = extracted_data.get("description", "").strip()
        date_string = extracted_data.get("date", "").strip()
        time_string = extracted_data.get("time", "").strip()
        destination = extracted_data.get("destination", "").strip()
        event_type = extracted_data.get("event_type", "").strip()

        plan_date = None
        plan_time = None

        if date_string:
            plan_date = datetime.strptime(
                date_string,
                "%Y-%m-%d"
            ).date()

        if time_string:
            plan_time = datetime.strptime(
                time_string,
                "%H:%M"
            ).time()

        weather_condition = ""
        temperature = ""
        rain_expected = False
        weather_advice = ""

        if destination and plan_date:

            try:
                weather = get_weather(destination, plan_date)

                if weather:
                    weather_condition = weather.get(
                        "weather_condition", ""
                    )

                    temperature = str(
                        weather.get("temperature", "")
                    )

                    rain_expected = weather.get(
                        "rain_expected", False
                    )

                    weather_advice = weather.get(
                        "weather_advice", ""
                    )

            except Exception:
                weather_condition = ""
                temperature = ""
                rain_expected = False
                weather_advice = ""

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

        final_response = AI_MODEL.generate_content(final_prompt)

        final_text = final_response.text.strip()

        if final_text.startswith("```"):
            final_text = final_text.replace("```json", "")
            final_text = final_text.replace("```", "")
            final_text = final_text.strip()

        final_data = json.loads(final_text)

        tasks = final_data.get("tasks", [])

        current_user = USER.objects.get(
            LOGIN=request.user
        )

        plan = Plans.objects.create(
            USER=current_user,
            title=title,
            description=description,
            date=plan_date,
            time=plan_time,
            status="pending",
            destination=destination,
            event_type=event_type,
            weather_condition=weather_condition,
            temperature=temperature,
            rain_expected=rain_expected,
            weather_advice=weather_advice
        )

        for task_text in tasks:

            if task_text:
                Task.objects.create(
                    PLANS=plan,
                    task=str(task_text).strip(),
                    completed=False
                )

        if plan_date and plan_time:

            event_datetime = timezone.make_aware(
                datetime.combine(
                    plan_date,
                    plan_time
                )
            )

            reminder_offsets = [
                (timedelta(hours=1), "1 hour"),
                (timedelta(minutes=30), "30 minutes"),
                (timedelta(minutes=10), "10 minutes")
            ]

            for offset, label in reminder_offsets:

                reminder_time = event_datetime - offset

                if reminder_time > current_datetime:

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
                        completed=False
                    )

        messages.success(
            request,
            "Your plan and reminders were created successfully."
        )

        return redirect("/myapp/home/")

    except json.JSONDecodeError:
        messages.error(
            request,
            "AI returned an invalid response. Please try again."
        )
        return redirect("/myapp/home/")

    except USER.DoesNotExist:
        messages.error(
            request,
            "User profile not found."
        )
        return redirect("/myapp/home/")

    except Exception as e:
        print("ANALYSER ERROR:", e)

        messages.error(
            request,
            "Something went wrong while creating your plan."
        )

        return redirect("/myapp/home/")




@login_required
def plans(request):
    ob=Plans.objects.filter(USER__LOGIN=request.user).order_by('-id')
    return render(request,'plans.html',{'plans': ob})


@login_required
def complete_task(request):

    if request.method != "POST":

        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid request method."
            }
        )

    try:

        data = json.loads(
            request.body
        )

        task_id = data.get(
            "task_id"
        )

        completed = data.get(
            "completed"
        )

        if task_id is None:

            return JsonResponse(
                {
                    "status": "error",
                    "message": "Task ID is required."
                }
            )

        task = Task.objects.get(
            id=task_id,
            PLANS__USER__LOGIN=request.user
        )

        task.completed = bool(
            completed
        )

        task.save()

        return JsonResponse(
            {
                "status": "success"
            }
        )

    except Task.DoesNotExist:

        return JsonResponse(
            {
                "status": "error",
                "message": "Task not found."
            },
            status=404
        )

    except Exception as e:

        print(
            "COMPLETE TASK ERROR:",
            repr(e)
        )

        return JsonResponse(
            {
                "status": "error",
                "message": "Could not update task."
            },
            status=500
        )


def view_history(request):
    today=datetime.now().date()
    ob=Plans.objects.filter(USER__LOGIN=request.user,date__lt=today).order_by('-date')
    return render(request,'history.html',{'data':ob})




def complete_reminder(request):

    if request.method == "POST":

        data = json.loads(request.body)

        reminder_id = data.get("reminder_id")
        completed = data.get("completed")

        try:

            reminder = Reminder.objects.get(
                id=reminder_id
            )

            reminder.completed = completed
            reminder.save()

            return JsonResponse({
                "status": "success"
            })

        except Reminder.DoesNotExist:

            return JsonResponse({
                "status": "error",
                "message": "Reminder not found"
            }, status=404)

    return JsonResponse({
        "status": "error"
    }, status=400)



def reminder_thread():
    while True:
        now = timezone.localtime()

        print("CURRENT:", now)
        

        reminders = Reminder.objects.filter(
            reminder_time__lte=now,
            notified=False
        )


        print("REMINDERS FOUND:", reminders.count())

        for reminder in reminders:
            print("SENDING:", reminder.message)

            toast = Notification(
                app_id="SmartGo AI",
                title="SmartGo Reminder",
                msg=reminder.message,
                duration="long"
            )

            toast.set_audio(audio.Default, loop=False)
            toast.show()

            reminder.notified = True
            reminder.save(update_fields=["notified"])

        time.sleep(10)

threading.Thread(
    target=reminder_thread,
    daemon=True
).start()