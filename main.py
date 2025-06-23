import os
import random
import requests
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets

# إعداد العنوان والوصف
TITLE = "مناظر طبيعية ساحرة | Breathtaking Nature Scenes"
DESCRIPTION = """
لقطات جميلة وهادئة من الحياة والطبيعة 🌿
استمتع بمشاهدة هذا الفيديو القصير الذي يمنحك راحة واسترخاء.
——
Beautiful and relaxing moments from nature 🌍
Enjoy this short peaceful video with calm visuals and music.
——
#استرخاء #مناظر_طبيعية #relaxing #nature #shorts
"""

# تحميل فيديو تجريبي من Pexels
VIDEO_URL = "https://player.vimeo.com/external/426969889.sd.mp4?s=3005c1f88662f0c61d8a58c552bdbbf0f4ae9c3b&profile_id=165"
AUDIO_URL = "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/no_curator/Chad_Crouch/Motion/Chad_Crouch_-_Moonrise.mp3"

VIDEO_FILE = "video.mp4"
AUDIO_FILE = "music.mp3"
FINAL_FILE = "final_output.mp4"

# تحميل الملفات
with open(VIDEO_FILE, 'wb') as f:
    f.write(requests.get(VIDEO_URL).content)
with open(AUDIO_FILE, 'wb') as f:
    f.write(requests.get(AUDIO_URL).content)

# دمج الفيديو والموسيقى
video = VideoFileClip(VIDEO_FILE).subclip(0, 55)
audio = AudioFileClip(AUDIO_FILE).volumex(0.5).subclip(0, 55)
final = video.set_audio(audio)
final.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")

# إعداد الاتصال بيوتيوب
flow = flow_from_clientsecrets("client_secret.json",
    scope="https://www.googleapis.com/auth/youtube.upload")
storage = Storage("oauth2.json")
credentials = storage.get()
if credentials is None or credentials.invalid:
    credentials = flow.run_console()
    storage.put(credentials)

youtube = build("youtube", "v3", credentials=credentials)

# رفع الفيديو
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": TITLE,
            "description": DESCRIPTION,
            "tags": ["nature", "relaxing", "shorts"]
        },
        "status": {
            "privacyStatus": "public"
        }
    },
    media_body=MediaFileUpload(FINAL_FILE)
)
response = request.execute()
print("✅ تم نشر الفيديو بنجاح. ID:", response["id"])
