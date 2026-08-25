from bse import BSE
import time, os, json

# ensure download folder exists
os.makedirs("downloads", exist_ok=True)

# initialize the BSE API object
b = BSE("downloads")

def load_latest():
    try:
        with open("latest.json") as f:
            return json.load(f).get("latest_id")
    except:
        return None

def save_latest(id):
    with open("latest.json", "w") as f:
        json.dump({"latest_id": id}, f)

latest_id = load_latest()
print("🔄 Watching for new BSE announcements... (Ctrl+C to stop)")

while True:
    data = b.get_data()  # this is the correct method in the repo
    if not data:
        time.sleep(10)
        continue

    newest = data[0]
    current_id = newest.get("NEWSID")

    if current_id != latest_id:
        print("\n🆕 New announcement detected!")
        print(f"Company : {newest.get('ScripName')}")
        print(f"Headline: {newest.get('HEADLINE')}")
        print(f"Time    : {newest.get('NEWS_DT')}")
        print(f"Link    : https://www.bseindia.com/corporates/ann.html?newsid={current_id}")
        latest_id = current_id
        save_latest(current_id)

    time.sleep(10)
