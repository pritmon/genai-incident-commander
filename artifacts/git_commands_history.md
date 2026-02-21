# Every Command We Used to Build This Project! 🚀

Here is the master list of all the terminal commands we ran to build, test, and upload our AI app, explained simply so anyone can understand what’s going on under the hood!

### 🏗️ Setting Up the Project Folders
**1.** `mkdir -p app data && mv main.py app/ && mv engine.py app/`
* **What it does:** This creates two new folders named `app` and `data`. Then, it moves (`mv`) our `main.py` and `engine.py` files straight into the `app` folder so our project looks neat and organized.

### 📦 Installing the Coding Tools
**2.** `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
* **What it does:** This is a big one! First, it creates a "virtual environment" (a safe, isolated sandbox for our code so it doesn't mess with the rest of your computer). Then, it activates that sandbox. Finally, it uses `pip` (Python's downloader) to install all the external libraries we need (like FastAPI and Google's AI tools) from our `requirements.txt` list.

### 🏃‍♂️ Running the Server
**3.** `source venv/bin/activate && uvicorn app.main:app --port 8000`
* **What it does:** It turns on the sandbox again and uses `uvicorn` (a super-fast server tool) to actually start up our FastAPI app on your computer at port 8000. This is like flipping the "Open for Business" sign on a store!

### 🧪 Testing the AI 
**4.** `curl -X POST -F "file=@data/rpa_logs.txt" http://localhost:8000/analyze`
* **What it does:** Have you ever submitted a form online? `curl` is a way to do that directly from the terminal. This command grabs our dummy text file (`rpa_logs.txt`) and throws it at our running server (`/analyze` endpoint) to see if the AI can read it and send back an answer.

**5.** `source venv/bin/activate && python list_models.py`
* **What it does:** We used this when we were debugging the Gemini API. It just runs a quick Python script to ask Google, "Hey, what AI models am I actually allowed to use right now?"

### 🛑 Fixing Stuck Ports
**6.** `lsof -ti :8000 | xargs kill -9`
* **What it does:** Sometimes the server crashes but secretly stays running in the background, blocking port 8000. This command acts like a sniper—it finds whichever background program is hogging port 8000 and forcefully shuts it down (`kill -9`) so we can restart cleanly.

### 🌐 Uploading the Code to GitHub
**7.** `git init && git add . && git commit -m "Initial commit of RPA Log Analyzer"`
* **What it does:** This is where we started version control! First, it tells Git to start watching the folder. Then it `add`s every single file we wrote to a staging area. Finally, it takes a permanent "snapshot" (`commit`) of the code and labels it "Initial commit".

**8.** `git branch -M main && git remote add origin https://github.com/pritmon/genai-incident-commander.git && git push -u origin main`
* **What it does:** This links your computer to the internet! It names your main timeline `main`, tells Git the exact web URL of your GitHub repository, and then `push`es (uploads) all our local code snapshots straight to the website for the whole world to see.

### 🧹 Cleaning Up
**9.** `mkdir -p artifacts && git mv git_commands_history.md artifacts/ && git commit -m "Move git commands history to artifacts folder" && git push origin main`
* **What it does:** This creates an `artifacts` folder, tells Git to safely move this very history file into it, takes a new snapshot of that change, and pushes the updated arrangement to GitHub!
