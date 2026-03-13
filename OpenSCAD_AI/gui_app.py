import os
import sys
import subprocess
import threading
import logging
import base64
from datetime import datetime
from typing import Optional, List
import customtkinter as ctk
from dotenv import load_dotenv

# Optional Image libs
try:
    from PIL import Image
    import io
    HAS_IMAGE = True
except ImportError:
    HAS_IMAGE = False

# Try importing Gemini, but handle failure gracefully
try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Try importing OpenAI for OpenRouter
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Configuration
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class Config:
    """Application configuration."""
    def __init__(self):
        load_dotenv()
        self.gemini_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.openrouter_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
        self.openscad_path: str = os.getenv("OPENSCAD_PATH", r"C:\Program Files\OpenSCAD\openscad.exe")
        self.output_file: str = "generated_model.scad"

class OpenSCADManager:
    """Manages OpenSCAD process and file operations."""
    def __init__(self, executable_path: str, output_file: str):
        self.executable_path = executable_path
        self.output_file = output_file
        self.process: Optional[subprocess.Popen] = None

    def save_code(self, code: str) -> str:
        """Saves the generated code to the output file."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(code)
            return f"Saved to {self.output_file}"
        except IOError as e:
            return f"Error saving file: {e}"

    def open_viewer(self) -> str:
        """Opens OpenSCAD with the output file."""
        if not os.path.exists(self.executable_path):
            return f"Error: OpenSCAD not found at {self.executable_path}"

        if self.process and self.process.poll() is None:
            return "OpenSCAD is already running."

        try:
            self.process = subprocess.Popen([self.executable_path, self.output_file])
            return "Launched OpenSCAD."
        except OSError as e:
            return f"Failed to launch OpenSCAD: {e}"

class LLMCoder:
    """Abstracts communication with LLM providers (Gemini or OpenRouter/OpenAI)."""
    
    SYSTEM_PROMPT = (
        "You are an expert OpenSCAD programmer (Senior Level). "
        "Your task is to convert natural language descriptions into valid, parametric OpenSCAD code.\n"
        
        "### CRITICAL CODING RULES:\n"
        "1. **Parametric Design:** ALWAYS define variables at the top (e.g., `width=10; height=20;`). Use these variables in the geometry.\n"
        "2. **Resolution:** Use a variable `$fn_val = 60;` and use `scad_resolution = $fn_val;` in your code. Allow user to change it.\n"
        "3. **Organic Shapes (IMPORTANT):** Do NOT try to build boats, cars, or animals using simple `union()` of cubes. "
        "   Instead, use **Sequential Hulling**. Define 2D profiles (slices) at different Z-heights and `hull()` them pairwise. "
        "   Example: `hull() { translate([0,0,0]) circle(10); translate([0,0,5]) circle(15); }`.\n"
        "4. **Cleanliness:** Output ONLY the raw OpenSCAD code. No markdown blocks (```), no explanations text outside comments.\n"
        "5. **Comments:** Explain complex math or logic with comments.\n"
        
        "### ITERATION RULES:\n"
        "1. You are in a continuous editing session.\n"
        "2. If the user asks to 'change X', return the **FULL** updated code file, not just the snippet.\n"
        "3. Maintain the variables defined in previous turns unless explicitly asked to change them."
    )

    def __init__(self, config: Config, model_name: str, logger_func):
        self.logger_func = logger_func
        self.config = config
        self.model_name = model_name
        self.provider = "unknown"
        self.client = None
        self.history = [] 
        self.gemini_chat = None
        self.current_image = None # Store base64 image if attached
        
        self._init_model()

    def _init_model(self):
        """Initializes the appropriate client based on model name."""
        
        # Determine provider
        if "gemini" in self.model_name.lower() and not self.model_name.startswith("google/"):
            # Native Google API (unless it's OpenRouter format like google/gemini...)
            self.provider = "google"
        else:
            # Assume OpenRouter/OpenAI compatible
            self.provider = "openrouter"

        self.logger_func(f"Initializing {self.provider.upper()} with model: {self.model_name}")

        if self.provider == "google":
            if not HAS_GEMINI:
                self.logger_func("Error: google-generativeai lib missing.")
                return
            if not self.config.gemini_key:
                self.logger_func("Error: GEMINI_API_KEY missing.")
                return
                
            try:
                genai.configure(api_key=self.config.gemini_key)
                self.client = genai.GenerativeModel(self.model_name)
                # Gemini handles system prompt differently, often better in the chat start
                self.gemini_chat = self.client.start_chat(history=[
                    {"role": "user", "parts": ["System Instruction: " + self.SYSTEM_PROMPT]},
                    {"role": "model", "parts": ["Understood. I am ready to generate parametric OpenSCAD code."]}
                ])
                self.logger_func("✓ Gemini Native initialized.")
            except Exception as e:
                self.logger_func(f"Error init Gemini: {e}")

        elif self.provider == "openrouter":
            if not HAS_OPENAI:
                self.logger_func("Error: openai lib missing.")
                return
            if not self.config.openrouter_key:
                self.logger_func("Error: OPENROUTER_API_KEY missing.")
                return

            try:
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.config.openrouter_key,
                )
                self.history = [{"role": "system", "content": self.SYSTEM_PROMPT}]
                self.logger_func("✓ OpenRouter initialized.")
            except Exception as e:
                self.logger_func(f"Error init OpenRouter: {e}")

    def update_model(self, model_name: str):
        self.model_name = model_name
        self.history = [] # Reset history on model switch usually safer
        self.gemini_chat = None
        self._init_model()

    def reset_history(self):
        if self.provider == "google" and self.client:
             self.gemini_chat = self.client.start_chat(history=[
                 {"role": "user", "parts": ["System Instruction: " + self.SYSTEM_PROMPT]},
                 {"role": "model", "parts": ["Understood."]}
             ])
        
        self.history = [{"role": "system", "content": self.SYSTEM_PROMPT}]

    def generate_scad(self, prompt: str) -> tuple[Optional[str], str]:
        """Generates OpenSCAD code from natural language prompt."""
        
        # Check for Strategy Injection
        strategy_prompt = ""
        user_prompt = prompt
        
        if "[STRATEGY: Organic (Hull)]" in prompt:
            user_prompt = prompt.replace("[STRATEGY: Organic (Hull)]", "").strip()
            strategy_prompt = (
                "\n### STRATEGY: SEQUENTIAL HULLING (Organic Shapes)\n"
                "1. **Do NOT** use simple `cube()` or `cylinder()` unions for the main body.\n"
                "2. Define a helper module `profile_2d(z)` that draws a 2D shape (circle/square/polygon) at a given height.\n"
                "3. Use `hull()` pairwise between these slices. Example:\n"
                "   `hull() { translate([0,0,0]) profile(10); translate([0,0,5]) profile(15); }`\n"
                "4. This creates smooth, lofted surfaces for boats, planes, or handles."
            )
        elif "[STRATEGY: Mechanical (CSG)]" in prompt:
            user_prompt = prompt.replace("[STRATEGY: Mechanical (CSG)]", "").strip()
            strategy_prompt = (
                "\n### STRATEGY: CONSTRUCTIVE SOLID GEOMETRY (Mechanical)\n"
                "1. Start with the main block (bounding box).\n"
                "2. Use `difference()` to carve out holes, slots, and screw countersinks.\n"
                "3. Use `union()` to add reinforcement ribs or mounting bosses.\n"
                "4. Use `minkowski()` ONLY if specifically asked for rounded edges (it is slow)."
            )
        elif "[STRATEGY: Lathe (Rotate)]" in prompt:
            user_prompt = prompt.replace("[STRATEGY: Lathe (Rotate)]", "").strip()
            strategy_prompt = (
                "\n### STRATEGY: PROFILE REVOLUTION (Lathe/Pottery)\n"
                "1. Define a list of 2D points `[[x1,z1], [x2,z2]...]` representing the **half-profile**.\n"
                "2. Use `polygon(points=...)` to create the 2D shape.\n"
                "3. Use `rotate_extrude($fn=100)` to spin it into 3D.\n"
                "4. Perfect for: vases, bottles, wheels, chess pieces."
            )

        full_prompt = f"{user_prompt}\n{strategy_prompt}"
        
        if not self.client:
             self._init_model()
             if not self.client:
                 return None, "Error: Client not initialized."

        self.logger_func(f"Sending request to {self.provider}...")

        try:
            if self.provider == "google":
                return self._generate_google(full_prompt)
            else:
                return self._generate_openrouter(full_prompt)
        except Exception as e:
            err_msg = f"API Error: {str(e)}"
            self.logger_func(f"❌ {err_msg}")
            return None, err_msg

    def _generate_google(self, prompt: str) -> tuple[Optional[str], str]:
        try:
            # Prepare contents
            contents = [prompt]
            if self.current_image:
                # Gemini native supports images differently, but for simplicity via chat
                # we might need to recreate the chat with image or send it as a separate part.
                # Currently simple text chat. To do multimodal properly in ChatSession is tricky.
                # Hack: if image, use generate_content on model directly (no history for image turn)
                # OR decode base64 to PIL Image for the library
                try:
                    image_data = base64.b64decode(self.current_image)
                    image = Image.open(io.BytesIO(image_data))
                    contents = [prompt, image]
                    
                    # For image requests, we often can't use the existing chat history object strictly
                    # if it was text-only. But Gemini 1.5 allows mix.
                    # Let's try sending to chat if possible, else direct model.
                    response = self.gemini_chat.send_message(contents)
                except Exception as img_err:
                    self.logger_func(f"Image Error: {img_err}")
                    response = self.gemini_chat.send_message(prompt)
            else:
                response = self.gemini_chat.send_message(prompt)

            code = self._clean_code(response.text)
            return code, "Success"
        except Exception as e:
            raise e

    def _generate_openrouter(self, prompt: str) -> tuple[Optional[str], str]:
        # Prepare message content (Text or Multimodal)
        message_content = [{"type": "text", "text": prompt}]
        
        if self.current_image:
            # OpenRouter / OpenAI format
            img_url = f"data:image/jpeg;base64,{self.current_image}"
            message_content.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
            
        # Add to history
        self.history.append({"role": "user", "content": message_content})
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.history,
                # Optional: specific OpenRouter headers if needed
                extra_headers={
                    "HTTP-Referer": "http://localhost:8000", # Required by OpenRouter
                    "X-Title": "OpenSCAD AI Assistant",
                },
            )
            
            content = completion.choices[0].message.content
            # Save assistant response as text only to history to avoid bloating
            self.history.append({"role": "assistant", "content": content})
            
            code = self._clean_code(content)
            return code, "Success"
        except Exception as e:
            raise e

    def _clean_code(self, text: str) -> str:
        # Improved cleanup to catch generic markdown blocks too
        clean = text.replace("```openscad", "").replace("```c", "").replace("```", "").strip()
        return clean

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = Config()
        self.manager = OpenSCADManager(self.config.openscad_path, self.config.output_file)
        self.coder = None
        
        # Models list - mixed providers
        # Note: OpenRouter allows any model ID. We list the most popular/powerful ones.
        self.available_models = [
            # --- Bleeding Edge (Nov 2025) ---
            "google/gemini-3-pro-preview",
            "openai/gpt-5.1-codex",
            "anthropic/claude-sonnet-4.5",

            # --- Google ---
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-pro-1.5",
            
            # --- Anthropic (Via OpenRouter) ---
            "anthropic/claude-3.5-sonnet",
            
            # --- OpenAI (Via OpenRouter) ---
            "openai/gpt-4o",
            "openai/o1-preview",
        ]
        self.current_model = self.available_models[0]

        # Window setup
        self.title("OpenSCAD AI Assistant")
        self.geometry("650x750")
        
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top Frame: Settings
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        self.settings_frame.grid_columnconfigure(3, weight=1)
        
        self.api_status_val = ctk.CTkLabel(self.settings_frame, text="Checking Config...", text_color="orange")
        self.api_status_val.grid(row=0, column=0, padx=10, pady=10)
        
        self.model_label = ctk.CTkLabel(self.settings_frame, text="Model:")
        self.model_label.grid(row=0, column=2, padx=(5,5), pady=10)
        
        self.model_selector = ctk.CTkComboBox(
            self.settings_frame, 
            values=self.available_models, 
            command=self.on_model_change, 
            width=250
        )
        self.model_selector.set(self.current_model)
        self.model_selector.grid(row=0, column=3, padx=(0,10), pady=10, sticky="w")

        # Main Input Area
        self.prompt_label = ctk.CTkLabel(self, text="Describe your 3D model:")
        self.prompt_label.grid(row=1, column=0, padx=10, pady=(10, 0), sticky="w")
        
        # Tools Frame (Upload & Strategy)
        self.tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tools_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.tools_frame.grid_columnconfigure(2, weight=1)

        self.upload_btn = ctk.CTkButton(self.tools_frame, text="📎 Attach Image/PDF", command=self.on_upload, width=150, fg_color="#555")
        self.upload_btn.grid(row=0, column=0, padx=5, sticky="w")
        
        self.file_label = ctk.CTkLabel(self.tools_frame, text="No file attached", text_color="gray")
        self.file_label.grid(row=0, column=1, padx=5, sticky="w")
        
        self.strategy_var = ctk.StringVar(value="Auto")
        self.strategy_combo = ctk.CTkComboBox(self.tools_frame, values=["Auto", "Organic (Hull)", "Mechanical (CSG)", "Lathe (Rotate)"], variable=self.strategy_var, width=150)
        self.strategy_combo.grid(row=0, column=3, padx=5, sticky="e")

        self.prompt_input = ctk.CTkTextbox(self, height=100)
        self.prompt_input.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")

        # Buttons
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)
        self.button_frame.grid_columnconfigure(2, weight=1)

        self.generate_btn = ctk.CTkButton(self.button_frame, text="Generate Code", command=self.on_generate)
        self.generate_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.clear_btn = ctk.CTkButton(self.button_frame, text="New Chat", command=self.on_clear_chat, fg_color="gray")
        self.clear_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.open_scad_btn = ctk.CTkButton(self.button_frame, text="Launch OpenSCAD", command=self.on_launch_scad, fg_color="green")
        self.open_scad_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        # Log/Output Area
        self.log_label = ctk.CTkLabel(self, text="Status / Logs:")
        self.log_label.grid(row=5, column=0, padx=10, pady=(10, 0), sticky="w")

        self.log_output = ctk.CTkTextbox(self, height=150, state="disabled")
        self.log_output.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        # Initialize Logic
        self.init_app()
        
        # Initial file creation
        if not os.path.exists(self.config.output_file):
            self.manager.save_code("// Generated code will appear here")

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        self.after(0, lambda: self._update_log_ui(formatted_msg))
    
    def _update_log_ui(self, message):
        self.log_output.configure(state="normal")
        self.log_output.insert("end", message + "\n")
        self.log_output.see("end")
        self.log_output.configure(state="disabled")

    def init_app(self):
        # Initialize coder with current model
        self.coder = LLMCoder(self.config, self.current_model, self.log)
        
        # Update status UI
        status_text = []
        if self.config.gemini_key: status_text.append("Gemini: OK")
        if self.config.openrouter_key: status_text.append("OpenRouter: OK")
        
        if status_text:
            self.api_status_val.configure(text=" | ".join(status_text), text_color="green")
        else:
            self.api_status_val.configure(text="No Keys Found (.env)", text_color="red")
            self.log("Warning: No API keys found in .env file.")

    def on_model_change(self, choice):
        # Allow custom manual entry if it's not in the list
        self.current_model = choice
        self.log(f"Switched model to: {choice}")
        if self.coder:
            self.coder.update_model(choice)

    def on_launch_scad(self):
        msg = self.manager.open_viewer()
        self.log(msg)

    def on_upload(self):
        file_path = ctk.filedialog.askopenfilename(
            title="Select Image or PDF",
            filetypes=[("Images & PDF", "*.jpg *.jpeg *.png *.pdf")]
        )
        if file_path:
            filename = os.path.basename(file_path)
            self.file_label.configure(text=filename, text_color="green")
            
            # Convert to base64
            try:
                with open(file_path, "rb") as image_file:
                    self.coder.current_image = base64.b64encode(image_file.read()).decode('utf-8')
                self.log(f"Attached: {filename}")
            except Exception as e:
                self.log(f"Error reading file: {e}")

    def on_clear_chat(self):
        """Resets the chat history."""
        if self.coder:
            self.coder.reset_history()
            self.file_label.configure(text="No file attached", text_color="gray")
            self.coder.current_image = None
            self.log("Chat history cleared. Starting fresh.")

    def on_generate(self):
        prompt = self.prompt_input.get("0.0", "end").strip()
        strategy = self.strategy_var.get()
        
        # Build prompt with strategy
        final_prompt = prompt
        if strategy != "Auto":
            final_prompt = f"[STRATEGY: {strategy}] {prompt}"
            
        if not final_prompt:
            self.log("Please enter a description.")
            return
        
        self.generate_btn.configure(state="disabled", text="Generating...")
        threading.Thread(target=self._generate_thread, args=(final_prompt,)).start()

    def _generate_thread(self, prompt):
        self.log(f"Generating code for: '{prompt[:30]}...'")
        code, status = self.coder.generate_scad(prompt)
        
        if code:
            save_msg = self.manager.save_code(code)
            self.log(save_msg)
            self.log("Done! Check OpenSCAD.")
        else:
            self.log(status)

        self.generate_btn.configure(state="normal", text="Generate Code")

if __name__ == "__main__":
    app = App()
    app.mainloop()
