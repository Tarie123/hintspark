# HintSpark
Interactive execution tracing for beginner Python learners. Flask backend + static web frontend.
NVIDIA NIM writes explanations; Google Gemini verifies them; deploys to Google Cloud Run.
See CONTRIBUTING.md to set up and add your part. Deploy: `gcloud run deploy hintspark --source . --region europe-west1 --allow-unauthenticated --set-env-vars NVIDIA_API_KEY=...,GEMINI_API_KEY=...`
