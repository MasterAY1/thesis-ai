# ThesisAI MVP

A brutal, practical MVP for evaluating nursing theses against the NMCN rubric.

## Project Structure
- `/frontend` - Next.js App Router with Tailwind CSS
- `/backend` - Python FastAPI server

## How to Run Locally

### 1. Start the Backend
Open a terminal in the `backend` folder:
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```
The backend will run at `http://localhost:8000`.

### 2. Start the Frontend
Open a new terminal in the `frontend` folder:
```bash
cd frontend
npm run dev
```
The frontend will run at `http://localhost:3000`.

### 3. Test the App
- Go to `http://localhost:3000`
- Upload any PDF
- Watch the mock evaluation process and view the Results Dashboard with the "Improve My Score" feedback loop.
