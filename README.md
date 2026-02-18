# 🎮 AI Game Builder

AI Game Builder is a Dockerized CLI tool that generates complete, playable browser games (HTML, CSS, and JavaScript) from a single text description.

Describe your game idea, and the tool instantly creates a canvas-based game with obstacles, level progression, and score tracking that runs locally in your browser.

---

## ✨ Features

- 🧠 Generates games from natural language prompts
- 🎮 HTML5 Canvas–based gameplay
- 👤 Username input with `localStorage` support
- 🚧 Obstacles and enemies
- 📈 Level-up popups
- 🏆 Score and leaderboard tracking
- 🐳 Fully Dockerized for easy execution

---

## 🛠 Tech Stack

- Python
- HTML, CSS, JavaScript
- HTML5 Canvas
- Docker
- Phaser


---

## 🚀 Getting Started

### Build the Docker Image

```bash
docker build -t game .
docker run -it game

