import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Optional

try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    from colorama import init, Fore, Style
except ImportError:
    print("Missing dependencies. Please run: pip install -r requirements.txt")
    sys.exit(1)

# Initialize colorama
init(autoreset=True)

class Config:
    """Application configuration."""
    def __init__(self):
        load_dotenv()
        self.api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        # Default to standard install location if not set
        self.openscad_path: str = os.getenv("OPENSCAD_PATH", r"C:\Program Files\OpenSCAD\openscad.exe")
        self.output_file: str = "generated_model.scad"

    def validate(self) -> bool:
        """Validates critical configuration."""
        if not self.api_key:
            print(f"{Fore.RED}Error: GEMINI_API_KEY not found in environment variables.")
            print(f"{Fore.YELLOW}Please create a .env file with your API key.")
            return False
        
        if not os.path.exists(self.openscad_path):
            print(f"{Fore.RED}Error: OpenSCAD executable not found at: {self.openscad_path}")
            print(f"{Fore.YELLOW}Please set OPENSCAD_PATH in .env to your installation path.")
            return False
            
        return True

class OpenSCADManager:
    """Manages OpenSCAD process and file operations."""
    
    def __init__(self, executable_path: str, output_file: str):
        self.executable_path = executable_path
        self.output_file = output_file
        self.process: Optional[subprocess.Popen] = None

    def save_code(self, code: str) -> None:
        """Saves the generated code to the output file."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(code)
            print(f"{Fore.GREEN}✓ Code saved to {self.output_file}")
        except IOError as e:
            print(f"{Fore.RED}Error saving file: {e}")

    def open_viewer(self) -> None:
        """Opens OpenSCAD with the output file if not already running."""
        # Note: OpenSCAD auto-reloads files, so we just need to ensure it's open.
        # Checking if specific process is running is complex cross-platform, 
        # so we'll just try to launch it. If user has it open, they should
        # just keep it open.
        
        if self.process and self.process.poll() is None:
            # Already running via this script
            return

        print(f"{Fore.CYAN}Launching OpenSCAD...")
        try:
            # Popen allows the script to continue running
            self.process = subprocess.Popen([self.executable_path, self.output_file])
        except OSError as e:
            print(f"{Fore.RED}Failed to launch OpenSCAD: {e}")

class GeminiCoder:
    """Handles communication with Gemini API."""
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def generate_scad(self, prompt: str) -> Optional[str]:
        """Generates OpenSCAD code from natural language prompt."""
        
        system_prompt = (
            "You are an expert OpenSCAD programmer. "
            "Your task is to convert natural language descriptions into valid OpenSCAD code. "
            "Rules:\n"
            "1. Output ONLY the raw OpenSCAD code. Do NOT use markdown code blocks (```). "
            "2. Do NOT include explanations outside of code comments. "
            "3. Use detailed comments in the code to explain complex parts. "
            "4. Make the code parametric where possible (use variables at the top). "
            "5. Ensure the code is valid and compiles."
        )
        
        full_prompt = f"{system_prompt}\n\nUser Request: {prompt}"
        
        print(f"{Fore.YELLOW}Generating code with Gemini...")
        try:
            response = self.model.generate_content(full_prompt)
            code = response.text
            
            # Cleanup potential markdown if the model ignores the rule
            code = code.replace("```openscad", "").replace("```", "").strip()
            
            return code
        except Exception as e:
            print(f"{Fore.RED}API Error: {e}")
            return None

def main():
    """Main application loop."""
    print(f"{Fore.BLUE}{Style.BRIGHT}=== OpenSCAD AI Assistant ==={Style.RESET_ALL}")
    
    config = Config()
    if not config.validate():
        sys.exit(1)
        
    manager = OpenSCADManager(config.openscad_path, config.output_file)
    coder = GeminiCoder(config.api_key)

    # Initial empty file if not exists
    if not os.path.exists(config.output_file):
        manager.save_code("// Generated OpenSCAD code will appear here")
    
    manager.open_viewer()
    
    print(f"{Fore.CYAN}Instructions:")
    print("1. Enter your description below.")
    print("2. OpenSCAD will update automatically.")
    print("3. Type 'exit' or 'quit' to close.")
    
    while True:
        try:
            user_input = input(f"\n{Fore.GREEN}You > {Style.RESET_ALL}").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
                
            if not user_input:
                continue
                
            code = coder.generate_scad(user_input)
            
            if code:
                manager.save_code(code)
                print(f"{Fore.BLUE}OpenSCAD should update momentarily.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"{Fore.RED}Unexpected error: {e}")

if __name__ == "__main__":
    main()

