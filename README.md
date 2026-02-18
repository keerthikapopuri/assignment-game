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

---

## 🚀 Quick Start

### Prerequisites
- Docker installed on your system

### One-Line Run

clone the repo

# Build and run
docker build -t ai-game-builder .
docker run -it ai-game-builder
---

## 🎯 How It Works

1. **You describe your game idea**
   ```
   Enter your game idea: a fox collecting berries while avoiding hunters
   ```

2. **AI asks clarifying questions**
   - What should the main character look like?
   - What obstacles should appear?
   - How does the game get harder?

3. **AI generates complete game files**
   - `index.html` - Game structure
   - `style.css` - Visual styling
   - `game.js` - Game logic

4. **Play instantly** - Open `index.html` in any browser

---

## 📁 Output Example

```
my_games/
├── game_generator/
│   ├── index.html
│   ├── style.css
│   ├── game.js
│
└── ...
```

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Clarification  │────▶│    Planning     │────▶│   Execution     │
│     Phase       │     │     Phase       │     │     Phase       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   Ask Questions          Create Tech Plan        Generate Files
   Extract Requirements   Define Mechanics        HTML/CSS/JS Code
```

---

## ⚖️ Trade-offs

- **LocalStorage** - No backend required
- **Fixed canvas size** - Consistent rendering
- **3 question limit** - Balances thoroughness with speed

---

## 🐳 Docker Commands

| Command | Description |
|---------|-------------|
| `docker build -t ai-game-builder .` | Build the image |
| `docker images` | List all images |
| `docker run -it ai-game-builder` | Run container |

---

## 🔮 Future Improvements

- Multi-model AI support (GPT-4, Claude)
- AI-generated sprites and sounds
- Mobile touch controls
- One-click deployment to GitHub Pages
- Multiplayer support
- Game analytics dashboard
