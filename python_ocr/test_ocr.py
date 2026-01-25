import requests
import sys
import json

def send_image_for_ocr(image_path):
    """
    Sends an image to the local OCR server and prints the response.
    """
    url = "http://127.0.0.1:5001/ocr"
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (image_path, f, 'image/png')}
            response = requests.post(url, files=files, timeout=10)

        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Error from server: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("Connection Error: Could not connect to the OCR server.")
        print("Please ensure the Flask server is running: 'python python_ocr/app.py'")
    except FileNotFoundError:
        print(f"Error: The file '{image_path}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_ocr.py <path_to_image>")
        sys.exit(1)
    
    image_path_arg = sys.argv[1]
    send_image_for_ocr(image_path_arg)
