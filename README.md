# Solvo - Ai Calculator (Backend)

Solvo is an AI-powered calculator web app that brings the intuitive, handwriting-based calculation experience of the iPad to any device. Write equations naturally using your finger, stylus, or mouse, and get instant, step-by-step solutions for arithmetic, algebra, calculus, and more.

## [Front end](https://github.com/reblox01/solvo.git)

## Features

- **Handwriting Recognition:** Input equations by writing directly on the screen.
- **Instant Computation:** Get immediate and accurate results for a wide range of math problems.
- **Step-by-Step Explanations:** Follow detailed breakdowns to learn how each problem is solved.
- **Responsive Design:** Fully accessible on desktops, tablets, and smartphones.
- **Interactive Learning:** Perfect for students, professionals, and math enthusiasts.

## Demo

Watch Solvo in action on YouTube (not available currently):  
[Solvo AI Calculator Demo](#)

## Installation

This repository contains the backend API implemented with FastAPI. The frontend (separate repo) is built with Node/React.

### Prerequisites (backend)

- Python 3.10 or later
- `pip` and `virtualenv` (or use `python -m venv`)

### Backend - Run locally

1. **Clone the repository and enter the project:**

   ```bash
   git clone https://github.com/yourusername/solvo.git
   cd solvo-backend
   ```

2. **Create and activate a virtual environment:**

   - macOS / Linux:

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

   - Windows (PowerShell):

     ```powershell
     python -m venv venv
     venv\Scripts\Activate.ps1
     ```

3. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set required environment variables:**

   Create a `.env` file in the project root with at least your Gemini API key:

   ```text
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

   The backend uses `python-dotenv` to load environment variables.

5. **Run the API (development):**

   You can run the server either with the included runner or directly with `uvicorn`:

   ```bash
   # Option A - run via the module (calls uvicorn)
   python main.py

   # Option B - run uvicorn with auto-reload
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **API endpoints (local):**

   - `GET /` - health/welcome message
   - `POST /analyze` - accepts an image file upload (`multipart/form-data`) and returns analysis
   - `POST /calculate` - accepts JSON image data (base64) and returns structured responses

Notes:

- The project includes a `Mangum` handler for serverless deployments (e.g., Vercel/Lambda).
- If you deploy to a serverless platform, follow that platform's deployment docs and ensure `GEMINI_API_KEY` is set in the environment.

## Usage

- **Input Equations:** Write equations on the canvas using your preferred input method.
- **View Results:** Solvo instantly recognizes your handwriting, computes the answer, and displays a step-by-step solution.
- **Learn:** Click on individual steps for additional insights and explanations.

## Technologies Used

- **Frontend:** React.js
- **Backend:** Node.js with Express (if applicable)
- **Machine Learning:** TensorFlow.js (for handwriting recognition)
- **Styling:** TailwindCSS, CSS/SCSS with modern UI libraries
- **Deployment:** Vercel (or your preferred cloud service like Docker/Heroku)

## Contributing

Contributions are welcome! To get started:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes and push your branch.
4. Open a pull request with a clear description of your changes.

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) when contributing.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For questions, suggestions, or feedback, please open an issue or contact us at [sohailkoutari@gmail.com](mailto:sohailkoutari@gmail.com).
