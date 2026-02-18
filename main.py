import os
import json
import requests
import logging
import re
import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Groq Client
class GroqClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "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")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
    
    def chat_completions_create(self, messages: list, model: str = "llama-3.1-8b-instant", 
                               temperature: float = 0.3, max_tokens: int = 4000):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return {"error": str(e), "choices": [{"message": {"content": "Error calling Groq API"}}]}

class UserManager:
    """Manages user profiles and scores."""
    
    def __init__(self):
        self.users_file = "users.json"
        self.current_user = None
        self.load_users()
    
    def load_users(self):
        """Load users from JSON file."""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    self.users = json.load(f)
            except:
                self.users = {}
        else:
            self.users = {}
    
    def save_users(self):
        """Save users to JSON file."""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def get_or_create_user(self, username: str) -> Dict:
        """Get existing user or create new one."""
        username = username.strip().lower()
        if username not in self.users:
            self.users[username] = {
                "username": username,
                "display_name": username.title(),
                "games_played": 0,
                "total_score": 0,
                "high_score": 0,
                "games_history": [],
                "created_at": datetime.datetime.now().isoformat(),
                "last_played": None
            }
            self.save_users()
        
        self.current_user = self.users[username]
        return self.current_user
    
    def update_user_score(self, game_title: str, score: int, level: int, won: bool):
        """Update user's score after playing a game."""
        if not self.current_user:
            return
        
        self.current_user["games_played"] += 1
        self.current_user["total_score"] += score
        self.current_user["last_played"] = datetime.datetime.now().isoformat()
        
        if score > self.current_user["high_score"]:
            self.current_user["high_score"] = score
        
        # Add to history
        self.current_user["games_history"].append({
            "game": game_title,
            "score": score,
            "level": level,
            "won": won,
            "date": datetime.datetime.now().isoformat()
        })
        
        # Keep only last 10 games
        if len(self.current_user["games_history"]) > 10:
            self.current_user["games_history"] = self.current_user["games_history"][-10:]
        
        self.save_users()
    
    def get_leaderboard(self) -> List[Dict]:
        """Get top players by high score."""
        leaderboard = []
        for username, data in self.users.items():
            leaderboard.append({
                "username": data["display_name"],
                "high_score": data["high_score"],
                "games_played": data["games_played"]
            })
        
        # Sort by high score descending
        leaderboard.sort(key=lambda x: x["high_score"], reverse=True)
        return leaderboard[:10]  # Top 10

class AgenticGameBuilder:
    def __init__(self, api_key: str = None):
        """Initialize the agent with Groq client."""
        self.client = GroqClient(api_key)
        self.conversation_history = []
        self.game_spec = {}
        self.max_clarifying_questions = 3
        self.user_manager = UserManager()
    
    def get_ai_response(self, prompt: str, system_message: str = None, temperature: float = 0.3, max_tokens: int = 2000) -> str:
        """Get response from Groq with conversation history."""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.extend(self.conversation_history[-6:])
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat_completions_create(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if "error" in response:
                logger.error(f"API Error: {response['error']}")
                return self._get_fallback_question()
            
            content = response["choices"][0]["message"]["content"]
            return content
        except Exception as e:
            logger.error(f"Error getting AI response: {e}")
            return self._get_fallback_question()
    
    def _get_fallback_question(self) -> str:
        """Provide fallback questions if API fails."""
        import random
        fallbacks = [
            "What should the main character be?",
            "What does the player need to collect?",
            "What obstacles should the player avoid?",
            "How does the game get harder?",
            "What happens when you lose?",
            "What's the visual style you want?",
            "How do you control the character?"
        ]
        return random.choice(fallbacks)
    
    def clarification_phase(self, initial_idea: str) -> Dict:
        """Phase 1: Ask clarifying questions until requirements are clear."""
        logger.info("Starting clarification phase...")
        
        system_message = """You are a game design expert. Your role is to ask clarifying questions 
        about the game idea. Be concise and ask only essential questions to understand:
        
        1. MAIN CHARACTER: What is it? (animal, person, object, etc.)
        2. MAIN ACTION: What does the character do? (collect, avoid, shoot, jump, etc.)
        3. COLLECTIBLES: What does the player collect? (coins, stars, items, etc.)
        4. OBSTACLES: What does the player need to avoid? (enemies, traps, barriers, etc.)
        5. PROGRESSION: How does the game get harder? (levels, speed, more obstacles, etc.)
        6. WIN/LOSE CONDITIONS: How do you win or lose?
        7. VISUAL STYLE: Any specific art style?
        
        Ask ONE question at a time. After each answer, decide if you need another question.
        When you have enough information, respond with "REQUIREMENTS_CLEAR" followed by a JSON 
        summary of the requirements.
        
        Example format:
        REQUIREMENTS_CLEAR{
            "character": "dog",
            "character_action": "runs and jumps to catch bones while avoiding enemies",
            "world_setting": "park with moving bones and enemy cats",
            "collectibles": "bones that move around",
            "obstacles": "enemy cats that patrol the area",
            "progression": "level up every 3 bones, bones move faster each level, more enemies appear",
            "win_condition": "reach level 10",
            "lose_condition": "hit by enemy or miss 5 bones",
            "controls": "arrow keys to move, space to jump",
            "visual_style": "cute cartoon"
        }"""
        
        self.conversation_history = [
            {"role": "user", "content": f"Game idea: {initial_idea}"}
        ]
        
        questions_asked = 0
        while questions_asked < self.max_clarifying_questions:
            # Get AI's next question
            response = self.get_ai_response(
                "Based on our conversation so far, what's your next clarifying question?",
                system_message,
                temperature=0.3
            )
            
            if "REQUIREMENTS_CLEAR" in response:
                try:
                    json_str = response.split("REQUIREMENTS_CLEAR")[1].strip()
                    requirements = json.loads(json_str)
                    logger.info("Requirements clarified successfully")
                    return requirements
                except Exception as e:
                    logger.error(f"Failed to parse requirements: {e}")
                    # Continue asking if parsing fails
            
            # Store and display the question
            self.conversation_history.append({"role": "assistant", "content": response})
            print(f"\n🤔 AI: {response}")
            user_response = input("Your answer: ")
            self.conversation_history.append({"role": "user", "content": user_response})
            
            questions_asked += 1
        
        # If we hit max questions, create requirements from the entire conversation
        return self._create_requirements_from_conversation()
    
    def _create_requirements_from_conversation(self) -> Dict:
        """Create requirements from the entire conversation using AI."""
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.conversation_history])
        
        prompt = f"""
Based on this entire conversation about a game idea:
{conversation_text}

Extract the key requirements into a JSON object with these fields:
- character: the main character
- character_action: what the character does
- world_setting: where the game takes place
- collectibles: what the player collects (if anything)
- obstacles: what the player avoids (if anything)
- progression: how the game gets harder
- win_condition: how to win
- lose_condition: how to lose
- controls: how to control the character
- visual_style: art style description

Return only the JSON object, no other text.

"""
        
        response = self.get_ai_response(prompt, temperature=0.1)
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                requirements = json.loads(json_match.group())
                return requirements
        except:
            pass
        
        # Fallback requirements
        return {
            "character": "player",
            "character_action": "moves and collects items while avoiding obstacles",
            "world_setting": "simple game world",
            "collectibles": "items",
            "obstacles": "enemies",
            "progression": "increasing difficulty with more obstacles",
            "win_condition": "reach target score",
            "lose_condition": "hit by obstacle",
            "controls": "arrow keys",
            "visual_style": "simple and colorful"
        }
    
    def planning_phase(self, requirements: Dict) -> Dict:
        """Phase 2: Create a detailed game plan."""
        logger.info("Starting planning phase...")
        
        system_message = """You are a game architect. Create a detailed technical plan for the game.
        Include:
        1. Framework choice (vanilla JS is simpler, Phaser for complex physics)
        2. Core game mechanics in detail (including obstacles)
        3. Game loop structure
        4. Data structures needed (for player, collectibles, obstacles)
        5. Key functions to implement
        6. File structure
        
        Output as JSON."""
        
        planning_prompt = f"""
Based on these requirements:
{json.dumps(requirements, indent=2)}

Create a comprehensive technical game plan. Be specific about how each mechanic will work.
Make sure to include obstacle mechanics as specified: {requirements.get('obstacles', 'none')}

Return as JSON with these keys:
- framework: "vanilla" or "phaser" (with reason)
- game_title: catchy title based on the concept
- mechanics: list of core mechanics (including obstacle avoidance)
- data_structures: what data to track (player, collectibles, obstacles)
- game_loop_steps: list of steps in each frame
- key_functions: list of functions to implement
- visual_elements: what to draw each frame (character, collectibles, obstacles)
"""
        
        response = self.get_ai_response(planning_prompt, system_message, temperature=0.2, max_tokens=2000)
        
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                self.game_spec = plan
                return plan
        except:
            pass
        
        # Create a simple plan if parsing fails
        return {
            "framework": "vanilla",
            "game_title": f"{requirements.get('character', 'Player')} {requirements.get('character_action', 'Game')}",
            "mechanics": [requirements.get('character_action', 'movement'), f"avoid {requirements.get('obstacles', 'obstacles')}"],
            "data_structures": ["player position", "score", "collectibles array", "obstacles array"],
            "game_loop_steps": ["handle input", "update positions", "check collisions with collectibles", "check collisions with obstacles", "draw"],
            "key_functions": ["init", "update", "draw", "checkCollectibleCollisions", "checkObstacleCollisions"],
            "visual_elements": ["character", "collectibles", "obstacles", "score display", "level display"]
        }
    
    def execution_phase(self, plan: Dict, requirements: Dict) -> Dict[str, str]:
        """Phase 3: Generate the actual game files using AI."""
        logger.info("Starting execution phase...")
        
        system_message = """You are an expert game developer. Create a complete, playable HTML5 game 
        based on the requirements and plan. The game must:
        
        1. Be fully functional in a browser with no external dependencies
        2. Use HTML5 Canvas for rendering
        3. Include all specified mechanics (including obstacles)
        4. Have proper game loop with requestAnimationFrame
        5. Handle user input correctly
        6. Include scoring and progression
        7. Have win/lose conditions as specified
        8. Include clear on-screen instructions
        9. Be visually appealing with CSS styling
        10. Include a username input field in the UI (not in terminal)
        11. Display leaderboard at the bottom of the page
        12. Show a popup with "Level {level}!" when leveling up
        13. Include obstacle mechanics exactly as specified
        
        Generate THREE files: index.html, style.css, and game.js
        
        IMPORTANT: 
        - The game MUST match the specific requirements EXACTLY
        - Include a username input field at the top of the game
        - Store username in localStorage and display it
        - Include obstacles as specified: {requirements.get('obstacles', 'enemies')}
        - Show a popup animation when leveling up with "Level {level}!"
        - The visuals should clearly show the theme
        - Include level progression exactly as specified
        - The code must be complete and run immediately when opened
        
        Format your response as a JSON object with keys: "index.html", "style.css", "game.js"
        Each value should be the complete file content as a string.
        """
        
        execution_prompt = f"""
REQUIREMENTS:
{json.dumps(requirements, indent=2)}

TECHNICAL PLAN:
{json.dumps(plan, indent=2)}

Create a complete, playable game that exactly matches these requirements.
The game should have:
- Main character: {requirements.get('character', 'player')}
- Main action: {requirements.get('character_action', 'movement')}
- Collectibles: {requirements.get('collectibles', 'items')}
- Obstacles: {requirements.get('obstacles', 'none')}
- Progression: {requirements.get('progression', 'levels get harder')}
- Win condition: {requirements.get('win_condition', 'reach target')}
- Lose condition: {requirements.get('lose_condition', 'hit obstacle')}
- Controls: {requirements.get('controls', 'arrow keys')}
- Visual style: {requirements.get('visual_style', 'colorful')}

CRITICAL FEATURES TO INCLUDE:
1. Username input field at the top of the game (save to localStorage)
2. Display current username in the game
3. Obstacles that move and cause game over on collision: {requirements.get('obstacles', 'enemies')}
4. Level up popup that appears and fades out showing "Level X!"
5. Leaderboard at the bottom showing top scores
6. Save score button when game ends

Make sure the game is fully playable and matches the theme exactly.
The character should LOOK like {requirements.get('character', 'a character')}
Collectibles should LOOK like {requirements.get('collectibles', 'items')}
Obstacles should LOOK like {requirements.get('obstacles', 'obstacles')}

Return ONLY a JSON object with the three files. No other text.
Strictly follow below output format:
{{
    "index.html": "<!DOCTYPE html>...</html>",
    "style.css": "body {{ ... }}",
    "game.js": "const canvas = document.getElementById('gameCanvas  '); ..."
}}

Strictly follow the output format mentioned above. The output must be in complete json format with no back ticks(`) included.
"""
        
        response = self.get_ai_response(execution_prompt, system_message, temperature=0.3, max_tokens=8000)
        print("response",response)
        try:
            # Try to parse JSON from response
            files = json.loads(re.sub(r"^```json\s*|\s*```$", "", response.strip(), flags=re.MULTILINE))
            print("files",files)
           #json_match = re.search(r'\{.*\}', response, re.DOTALL)
            # if json_match:
            #     files = json.loads(json_match.group())
                # Validate we have all required files
            if all(key in files for key in ["index.html", "style.css", "game.js"]):
                # Enhance with user input and obstacle features
                files = self._enhance_game_files(files, requirements)
                self._save_files(files)
                return files
            else:
                logger.error(f"Missing required files. Got: {list(files.keys())}")
        except Exception as e:
            logger.error(f"Failed to parse game files: {e}")
        
        # If AI generation fails, create a themed fallback with all features
        logger.warning("AI generation failed, using enhanced fallback template")
        files = self._create_enhanced_fallback(requirements, plan)
        self._save_files(files)
        return files
    
    def _enhance_game_files(self, files: Dict[str, str], requirements: Dict) -> Dict[str, str]:
        """Enhance game files with username input, obstacles, and level popups."""
        
        # Get obstacle info
        obstacles = requirements.get('obstacles', 'enemies')
        
        # Enhance game.js with better level popup and obstacles
        if "game.js" in files:
            game_js = files["game.js"]
            
            # Add enhanced level up popup function
            level_popup_code = """
// Enhanced level up popup
function showLevelUp() {
    const level = game.level;
    const popup = document.createElement('div');
    popup.className = 'level-popup';
    popup.innerHTML = `
        <div class="popup-content">
            <div class="popup-icon">⭐</div>
            <div class="popup-text">Level ${level}!</div>
        </div>
    `;
    document.body.appendChild(popup);
    
    // Animate and remove
    setTimeout(() => {
        popup.classList.add('fade-out');
        setTimeout(() => popup.remove(), 500);
    }, 1500);
}

// Replace existing level up code with popup
const originalLevelUp = checkLevelUp;
checkLevelUp = function() {
    if (originalLevelUp) originalLevelUp();
    showLevelUp();
};
"""
            
            # Insert level popup code
            game_js = level_popup_code + "\n" + game_js
            files["game.js"] = game_js
        
        # Enhance index.html with username input
        if "index.html" in files:
            html = files["index.html"]
            
            username_section = """
    <!-- Username Section -->
    <div class="username-section">
        <div class="username-container">
            <label for="username">👤 Player Name:</label>
            <input type="text" id="username" placeholder="Enter your name" maxlength="20">
            <button onclick="saveUsername()">Save</button>
            <span id="currentUser" class="current-user"></span>
        </div>
    </div>
"""
            
            # Insert username section at the top
            html = html.replace('<body>', '<body>\n' + username_section)
            
            # Add username script
            username_script = """
<script>
// Username management
function saveUsername() {
    const username = document.getElementById('username').value.trim();
    if (username) {
        localStorage.setItem('gameUsername', username);
        document.getElementById('currentUser').innerHTML = `Playing as: <strong>${username}</strong>`;
        document.getElementById('username').value = '';
    }
}

// Load username on page load
window.addEventListener('load', function() {
    const savedUsername = localStorage.getItem('gameUsername');
    if (savedUsername) {
        document.getElementById('currentUser').innerHTML = `Playing as: <strong>${savedUsername}</strong>`;
    }
});
</script>
"""
            
            # Insert script before closing body
            html = html.replace('</body>', username_script + '\n</body>')
            files["index.html"] = html
        
        # Enhance style.css with popup styles
        if "style.css" in files:
            css = files["style.css"]
            
            popup_styles = """
/* Level Popup Styles */
.level-popup {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    pointer-events: none;
    z-index: 9999;
    animation: popupAppear 0.3s ease-out;
}

.popup-content {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px 60px;
    border-radius: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    text-align: center;
    transform: scale(0);
    animation: popupScale 0.3s ease-out forwards;
}

.popup-icon {
    font-size: 48px;
    margin-bottom: 10px;
}

.popup-text {
    font-size: 36px;
    font-weight: bold;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.level-popup.fade-out {
    animation: fadeOut 0.5s ease-out forwards;
}

@keyframes popupAppear {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes popupScale {
    from { transform: scale(0); }
    to { transform: scale(1); }
}

@keyframes fadeOut {
    from { opacity: 1; }
    to { opacity: 0; }
}

/* Username Section Styles */
.username-section {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 20px;
    color: white;
}

.username-container {
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
    justify-content: center;
}

.username-container label {
    font-weight: bold;
    font-size: 16px;
}

.username-container input {
    padding: 8px 15px;
    border: none;
    border-radius: 5px;
    font-size: 14px;
    flex: 1;
    min-width: 200px;
}

.username-container button {
    padding: 8px 20px;
    background: #ff6b6b;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-weight: bold;
    transition: transform 0.2s;
}

.username-container button:hover {
    transform: scale(1.05);
    background: #ff5252;
}

.current-user {
    font-size: 16px;
    padding: 5px 15px;
    background: rgba(255,255,255,0.2);
    border-radius: 20px;
}

/* Obstacle Styles (will be used in game.js) */
.obstacle {
    transition: transform 0.1s;
}

.obstacle-danger {
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.1); }
    100% { transform: scale(1); }
}
"""
            files["style.css"] = css + "\n" + popup_styles
        
        return files
    
    def _create_enhanced_fallback(self, requirements: Dict, plan: Dict) -> Dict[str, str]:
        """Create an enhanced fallback game with all features."""
        character = requirements.get('character', 'Player')
        collectible = requirements.get('collectibles', 'items')
        obstacles = requirements.get('obstacles', 'enemies')
        action = requirements.get('character_action', 'collects')
        controls = requirements.get('controls', 'arrow keys')
        
        return {
            "index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{character} {action} {collectible}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <!-- Username Section -->
    <div class="username-section">
        <div class="username-container">
            <label for="username">👤 Player Name:</label>
            <input type="text" id="username" placeholder="Enter your name" maxlength="20">
            <button onclick="saveUsername()">Save</button>
            <span id="currentUser" class="current-user"></span>
        </div>
    </div>
    
    <div class="game-wrapper">
        <h1>{character} {action} {collectible}</h1>
        
        <div class="stats">
            <div class="stat">Score: <span id="score">0</span></div>
            <div class="stat">Level: <span id="level">1</span></div>
            <div class="stat">Time: <span id="timer">30</span>s</div>
        </div>
        
        <canvas id="gameCanvas" width="800" height="400"></canvas>
        
        <div class="controls">
            <p>Controls: {controls}</p>
            <p>Collect {collectible} to score. Avoid {obstacles}! Level up every 3 collected.</p>
        </div>
        
        <button onclick="resetGame()">New Game</button>
        <button id="saveScoreBtn" class="save-score-btn" style="display:none;" onclick="saveCurrentScore()">Save Score to Leaderboard</button>
    </div>
    
    <!-- Leaderboard Section -->
    <div class="leaderboard-section">
        <div id="leaderboard" class="leaderboard">
            <h3>🏆 Leaderboard</h3>
            <p>Loading...</p>
        </div>
    </div>
    
    <script src="game.js"></script>
</body>
</html>""",
            
            "style.css": f"""* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px;
}}

/* Username Section */
.username-section {{
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 20px;
    width: 100%;
    max-width: 900px;
    color: white;
}}

.username-container {{
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
    justify-content: center;
}}

.username-container label {{
    font-weight: bold;
    font-size: 16px;
}}

.username-container input {{
    padding: 8px 15px;
    border: none;
    border-radius: 5px;
    font-size: 14px;
    flex: 1;
    min-width: 200px;
}}

.username-container button {{
    padding: 8px 20px;
    background: #ff6b6b;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-weight: bold;
    transition: transform 0.2s;
}}

.username-container button:hover {{
    transform: scale(1.05);
    background: #ff5252;
}}

.current-user {{
    font-size: 16px;
    padding: 5px 15px;
    background: rgba(255,255,255,0.2);
    border-radius: 20px;
}}

.game-wrapper {{
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    text-align: center;
    max-width: 900px;
    width: 100%;
}}

h1 {{
    color: #333;
    margin-bottom: 20px;
    text-transform: capitalize;
}}

.stats {{
    display: flex;
    justify-content: space-around;
    margin-bottom: 20px;
    font-size: 18px;
}}

.stat {{
    background: #f0f0f0;
    padding: 10px 20px;
    border-radius: 10px;
    font-weight: bold;
}}

.stat span {{
    color: #667eea;
    font-size: 24px;
    margin-left: 5px;
}}

#gameCanvas {{
    border: 3px solid #333;
    border-radius: 10px;
    background: #f9f9f9;
    margin-bottom: 20px;
    width: 100%;
    height: auto;
}}

.controls {{
    margin: 20px 0;
    color: #666;
    line-height: 1.6;
}}

button {{
    background: #667eea;
    color: white;
    border: none;
    padding: 12px 40px;
    border-radius: 25px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
    transition: transform 0.2s, background 0.2s;
    margin: 5px;
}}

button:hover {{
    background: #764ba2;
    transform: scale(1.05);
}}

.save-score-btn {{
    background: #4CAF50;
}}

.save-score-btn:hover {{
    background: #45a049;
}}

/* Leaderboard Section */
.leaderboard-section {{
    margin-top: 30px;
    padding: 20px;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    width: 100%;
    max-width: 900px;
}}

.leaderboard {{
    max-width: 600px;
    margin: 0 auto;
}}

.leaderboard h3 {{
    color: #333;
    text-align: center;
    margin-bottom: 15px;
    font-size: 24px;
}}

.leaderboard ol {{
    list-style: none;
    padding: 0;
}}

.leaderboard li {{
    padding: 10px;
    margin: 5px 0;
    background: white;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
}}

.leaderboard li:first-child {{
    background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
    color: white;
    font-weight: bold;
}}

.leaderboard li:nth-child(2) {{
    background: linear-gradient(135deg, #C0C0C0 0%, #A0A0A0 100%);
    color: white;
}}

.leaderboard li:nth-child(3) {{
    background: linear-gradient(135deg, #CD7F32 0%, #8B4513 100%);
    color: white;
}}

/* Level Popup Styles */
.level-popup {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    pointer-events: none;
    z-index: 9999;
    animation: popupAppear 0.3s ease-out;
}}

.popup-content {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px 60px;
    border-radius: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    text-align: center;
    transform: scale(0);
    animation: popupScale 0.3s ease-out forwards;
}}

.popup-icon {{
    font-size: 48px;
    margin-bottom: 10px;
}}

.popup-text {{
    font-size: 36px;
    font-weight: bold;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}}

.level-popup.fade-out {{
    animation: fadeOut 0.5s ease-out forwards;
}}

@keyframes popupAppear {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}

@keyframes popupScale {{
    from {{ transform: scale(0); }}
    to {{ transform: scale(1); }}
}}

@keyframes fadeOut {{
    from {{ opacity: 1; }}
    to {{ opacity: 0; }}
}}""",
            
            "game.js": f"""// Game configuration
const CONFIG = {{
    canvasWidth: 800,
    canvasHeight: 400,
    playerSize: 30,
    playerSpeed: 5,
    collectibleSize: 20,
    obstacleSize: 25,
    baseCollectibleSpeed: 2,
    baseObstacleSpeed: 2.5,
    spawnInterval: 1000,
    obstacleSpawnInterval: 1500,
    timePerLevel: 30,
    maxLevel: 10
}};

// Username management
let currentUsername = localStorage.getItem('gameUsername') || 'Guest';

function saveUsername() {{
    const username = document.getElementById('username').value.trim();
    if (username) {{
        localStorage.setItem('gameUsername', username);
        currentUsername = username;
        document.getElementById('currentUser').innerHTML = `Playing as: <strong>${{username}}</strong>`;
        document.getElementById('username').value = '';
    }}
}}

// Load username on startup
window.addEventListener('load', function() {{
    const saved = localStorage.getItem('gameUsername');
    if (saved) {{
        currentUsername = saved;
        document.getElementById('currentUser').innerHTML = `Playing as: <strong>${{saved}}</strong>`;
    }}
}});

// Leaderboard
let leaderboard = [];

function loadLeaderboard() {{
    const saved = localStorage.getItem('gameLeaderboard');
    if (saved) {{
        leaderboard = JSON.parse(saved);
    }}
    displayLeaderboard();
}}

function saveScore(score, level, won) {{
    const entry = {{
        username: currentUsername,
        score: score,
        level: level,
        won: won,
        date: new Date().toISOString()
    }};
    
    leaderboard.push(entry);
    leaderboard.sort((a, b) => b.score - a.score);
    leaderboard = leaderboard.slice(0, 10);
    
    localStorage.setItem('gameLeaderboard', JSON.stringify(leaderboard));
    displayLeaderboard();
}}

function displayLeaderboard() {{
    const leaderboardEl = document.getElementById('leaderboard');
    if (!leaderboardEl) return;
    
    let html = '<h3>🏆 Leaderboard</h3>';
    if (leaderboard.length === 0) {{
        html += '<p>No scores yet. Be the first!</p>';
    }} else {{
        html += '<ol>';
        leaderboard.forEach((entry, index) => {{
            const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '📌';
            html += `<li>${{medal}} ${{entry.username}}: ${{entry.score}} points (Level ${{entry.level}})</li>`;
        }});
        html += '</ol>';
    }}
    
    leaderboardEl.innerHTML = html;
}}

// Level popup
function showLevelUp() {{
    const level = game.level;
    const popup = document.createElement('div');
    popup.className = 'level-popup';
    popup.innerHTML = `
        <div class="popup-content">
            <div class="popup-icon">⭐</div>
            <div class="popup-text">Level ${{level}}!</div>
        </div>
    `;
    document.body.appendChild(popup);
    
    setTimeout(() => {{
        popup.classList.add('fade-out');
        setTimeout(() => popup.remove(), 500);
    }}, 1500);
}}

// Game state
let game = {{
    score: 0,
    level: 1,
    timeLeft: CONFIG.timePerLevel,
    gameRunning: true,
    player: {{
        x: 400,
        y: 350,
        size: CONFIG.playerSize
    }},
    collectibles: [],
    obstacles: []
}};

// DOM elements
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const scoreElement = document.getElementById('score');
const levelElement = document.getElementById('level');
const timerElement = document.getElementById('timer');

// Controls
const keys = {{}};
document.addEventListener('keydown', (e) => keys[e.key] = true);
document.addEventListener('keyup', (e) => keys[e.key] = false);

// Timers
let spawnInterval;
let obstacleInterval;
let gameTimer;

function startGame() {{
    game = {{
        score: 0,
        level: 1,
        timeLeft: CONFIG.timePerLevel,
        gameRunning: true,
        player: {{
            x: 400,
            y: 350,
            size: CONFIG.playerSize
        }},
        collectibles: [],
        obstacles: []
    }};
    
    updateDisplay();
    document.getElementById('saveScoreBtn').style.display = 'none';
    
    // Clear old intervals
    if (spawnInterval) clearInterval(spawnInterval);
    if (obstacleInterval) clearInterval(obstacleInterval);
    if (gameTimer) clearInterval(gameTimer);
    
    // Start new intervals
    spawnInterval = setInterval(spawnCollectible, CONFIG.spawnInterval);
    obstacleInterval = setInterval(spawnObstacle, CONFIG.obstacleSpawnInterval);
    gameTimer = setInterval(updateTimer, 1000);
}}

function spawnCollectible() {{
    if (!game.gameRunning) return;
    
    const speedMultiplier = 1 + (game.level - 1) * 0.2;
    game.collectibles.push({{
        x: canvas.width,
        y: Math.random() * (canvas.height - 100) + 50,
        size: CONFIG.collectibleSize,
        speed: CONFIG.baseCollectibleSpeed * speedMultiplier,
        collected: false
    }});
}}

function spawnObstacle() {{
    if (!game.gameRunning) return;
    
    const speedMultiplier = 1 + (game.level - 1) * 0.25;
    game.obstacles.push({{
        x: canvas.width,
        y: Math.random() * (canvas.height - 100) + 50,
        size: CONFIG.obstacleSize,
        speed: CONFIG.baseObstacleSpeed * speedMultiplier
    }});
}}

function updateTimer() {{
    if (!game.gameRunning) return;
    
    game.timeLeft--;
    timerElement.textContent = game.timeLeft;
    
    if (game.timeLeft <= 0) {{
        gameOver("Time's up!");
    }}
}}

function update() {{
    if (!game.gameRunning) return;
    
    // Move player
    if (keys['ArrowLeft'] || keys['a']) game.player.x -= CONFIG.playerSpeed;
    if (keys['ArrowRight'] || keys['d']) game.player.x += CONFIG.playerSpeed;
    if (keys['ArrowUp'] || keys['w']) game.player.y -= CONFIG.playerSpeed;
    if (keys['ArrowDown'] || keys['s']) game.player.y += CONFIG.playerSpeed;
    
    // Keep player in bounds
    game.player.x = Math.max(0, Math.min(canvas.width - game.player.size, game.player.x));
    game.player.y = Math.max(0, Math.min(canvas.height - game.player.size, game.player.y));
    
    // Move collectibles and check collisions
    for (let i = game.collectibles.length - 1; i >= 0; i--) {{
        const item = game.collectibles[i];
        item.x -= item.speed;
        
        // Check collision with player
        if (!item.collected &&
            game.player.x < item.x + item.size &&
            game.player.x + game.player.size > item.x &&
            game.player.y < item.y + item.size &&
            game.player.y + game.player.size > item.y) {{
            
            item.collected = true;
            game.score += 10;
            game.collectibles.splice(i, 1);
            
            // Check level up (every 3 items)
            if (game.score % 30 === 0) {{
                game.level++;
                levelElement.textContent = game.level;
                game.timeLeft = CONFIG.timePerLevel;
                showLevelUp();
                
                if (game.level >= CONFIG.maxLevel) {{
                    win();
                }}
            }}
        }}
        // Remove if off screen
        else if (item.x + item.size < 0) {{
            game.collectibles.splice(i, 1);
        }}
    }}
    
    // Move obstacles and check collisions
    for (let i = game.obstacles.length - 1; i >= 0; i--) {{
        const obstacle = game.obstacles[i];
        obstacle.x -= obstacle.speed;
        
        // Check collision with player
        if (game.player.x < obstacle.x + obstacle.size &&
            game.player.x + game.player.size > obstacle.x &&
            game.player.y < obstacle.y + obstacle.size &&
            game.player.y + game.player.size > obstacle.y) {{
            
            gameOver("Hit by {obstacles}!");
            return;
        }}
        
        // Remove if off screen
        if (obstacle.x + obstacle.size < 0) {{
            game.obstacles.splice(i, 1);
        }}
    }}
    
    updateDisplay();
}}

function updateDisplay() {{
    scoreElement.textContent = game.score;
    levelElement.textContent = game.level;
}}

function gameOver(message) {{
    game.gameRunning = false;
    clearInterval(spawnInterval);
    clearInterval(obstacleInterval);
    clearInterval(gameTimer);
    
    const popup = document.createElement('div');
    popup.className = 'level-popup';
    popup.innerHTML = `
        <div class="popup-content" style="background: linear-gradient(135deg, #ff6b6b 0%, #ff5252 100%);">
            <div class="popup-icon">💀</div>
            <div class="popup-text">${{message}}</div>
        </div>
    `;
    document.body.appendChild(popup);
    
    setTimeout(() => {{
        popup.classList.add('fade-out');
        setTimeout(() => popup.remove(), 500);
    }}, 2000);
    
    document.getElementById('saveScoreBtn').style.display = 'inline-block';
}}

function win() {{
    game.gameRunning = false;
    clearInterval(spawnInterval);
    clearInterval(obstacleInterval);
    clearInterval(gameTimer);
    
    const popup = document.createElement('div');
    popup.className = 'level-popup';
    popup.innerHTML = `
        <div class="popup-content" style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);">
            <div class="popup-icon">🏆</div>
            <div class="popup-text">YOU WIN!</div>
        </div>
    `;
    document.body.appendChild(popup);
    
    setTimeout(() => {{
        popup.classList.add('fade-out');
        setTimeout(() => popup.remove(), 500);
    }}, 2000);
    
    document.getElementById('saveScoreBtn').style.display = 'inline-block';
}}

function saveCurrentScore() {{
    saveScore(game.score, game.level, game.level >= CONFIG.maxLevel);
    document.getElementById('saveScoreBtn').style.display = 'none';
}}

function draw() {{
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw background
    ctx.fillStyle = '#f0f0f0';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw collectibles
    game.collectibles.forEach(item => {{
        ctx.fillStyle = '#FFD700';
        ctx.beginPath();
        ctx.arc(item.x + item.size/2, item.y + item.size/2, item.size/2, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.fillStyle = '#FFA500';
        ctx.beginPath();
        ctx.arc(item.x + item.size/2 - 3, item.y + item.size/2 - 3, 3, 0, Math.PI * 2);
        ctx.fill();
    }});
    
    // Draw obstacles
    game.obstacles.forEach(obstacle => {{
        ctx.fillStyle = '#ff4444';
        ctx.beginPath();
        ctx.arc(obstacle.x + obstacle.size/2, obstacle.y + obstacle.size/2, obstacle.size/2, 0, Math.PI * 2);
        ctx.fill();
        
        // Draw danger symbol
        ctx.fillStyle = 'white';
        ctx.font = 'bold 16px Arial';
        ctx.fillText('⚠', obstacle.x + obstacle.size/2 - 8, obstacle.y + obstacle.size/2 + 5);
    }});
    
    // Draw player (character)
    ctx.fillStyle = '#4CAF50';
    ctx.fillRect(game.player.x, game.player.y, game.player.size, game.player.size);
    
    // Add eyes
    ctx.fillStyle = 'white';
    ctx.beginPath();
    ctx.arc(game.player.x + 8, game.player.y + 8, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(game.player.x + 22, game.player.y + 8, 4, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.fillStyle = 'black';
    ctx.beginPath();
    ctx.arc(game.player.x + 8, game.player.y + 8, 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(game.player.x + 22, game.player.y + 8, 2, 0, Math.PI * 2);
    ctx.fill();
    
    // Add label
    ctx.fillStyle = '#333';
    ctx.font = '12px Arial';
    ctx.fillText("{character}", game.player.x, game.player.y - 5);
}}

function gameLoop() {{
    update();
    draw();
    requestAnimationFrame(gameLoop);
}}

function resetGame() {{
    startGame();
}}

// Initialize
loadLeaderboard();
startGame();
gameLoop();

// Prevent page scrolling
window.addEventListener('keydown', (e) => {{
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {{
        e.preventDefault();
    }}
}});"""
        }
    
    def _save_files(self, files: Dict[str, str]):
        output_dir = "generated_game"
        os.makedirs(output_dir, exist_ok=True)

        for filename, content in files.items():
            filepath = os.path.join(output_dir, filename)

            # ✅ Force UTF-8 encoding
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Saved {filepath}")
    
    def run(self, initial_idea: str):
        """Run the complete agent workflow."""
        logger.info(f"Starting game builder for: {initial_idea}")
        
        print("\n" + "="*60)
        print("🎮 AGENTIC GAME BUILDER AI")
        print("="*60)
        
        print(f"\n📝 Your idea: {initial_idea}")
        
        # Phase 1: Clarification
        print("\n" + "📋"*30)
        print("PHASE 1: Let me understand your game idea")
        print("📋"*30)
        requirements = self.clarification_phase(initial_idea)
        print(f"\n✅ Requirements gathered:")
        for key, value in requirements.items():
            print(f"   • {key.replace('_', ' ').title()}: {value}")
        
        # Phase 2: Planning
        print("\n" + "📐"*30)
        print("PHASE 2: Creating game architecture")
        print("📐"*30)
        plan = self.planning_phase(requirements)
        print(f"\n✅ Game plan created for: {plan.get('game_title', 'Your Game')}")
        
        # Phase 3: Execution
        print("\n" + "⚙️"*30)
        print("PHASE 3: Generating your game...")
        print("⚙️"*30)
        print("   This may take a moment (the AI is writing code)...")
        files = self.execution_phase(plan, requirements)
        
        print("\n" + "="*60)
        print("✅ GAME READY! 🎮")
        print("="*60)
        print("\n📁 Files created in 'generated_game' folder:")
        for filename in files.keys():
            print(f"   • {filename}")
        
        print("\n🎯 To play your game:")
        print("   1. Open the 'generated_game' folder")
        print("   2. Double-click 'index.html' to play in your browser")
        print("\n   Features in your game:")
        print("   • Enter username in the UI (not terminal)")
        print(f"   • Avoid {requirements.get('obstacles', 'obstacles')}")
        print("   • Level up popup with animation")
        print("   • Leaderboard at the bottom")
        
        print("\nEnjoy your custom game! 🕹️")


def main():
    """Main entry point."""
    print("\n" + "🌟"*30)
    print("  WELCOME TO THE AI GAME BUILDER")
    print("🌟"*30)
    print("\nI can create ANY game you describe!")
    print("Your game will have:")
    print("   • Username input in the UI")
    print("   • Obstacles to avoid")
    print("   • Level up popups")
    print("   • Leaderboard tracking\n")
    
    print("Example ideas:")
    print("  • 'A dog fetching bones in a park, avoiding cats, level up every 3 bones'")
    print("  • 'A penguin catching fish while avoiding sharks, with level popups'")
    print("  • 'A robot collecting coins while avoiding lasers, level up animation'")
    print("  • 'A butterfly collecting nectar while avoiding birds, show Level X! popup'\n")
    
    initial_idea = input("Your game idea: ").strip()
    
    if not initial_idea:
        initial_idea = "A character collecting items while avoiding enemies, with level up popups"
        print(f"\nUsing default idea: {initial_idea}")
    
    # Check for API key
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("\n⚠️  Note: Using default Groq API key (may have rate limits)")
        print("   For better results, create a .env file with your GROQ_API_KEY\n")
    
    agent = AgenticGameBuilder()
    
    try:
        agent.run(initial_idea)
    except KeyboardInterrupt:
        print("\n\n👋 Game building cancelled. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Please try again with a different idea.")


if __name__ == "__main__":
    main()