# LiveJournal 2 Markdown Archive Tool

This script is a utility to download, archive, and convert LiveJournal posts into markdown (`.md`) files. It provides an automated solution to backup LiveJournal blogs, preserving each post's content, title, and publishing date for posts that are public.

## Features:
- Fetches all post permalinks from the provided LiveJournal blog.
- Downloads each post and saves it as a markdown file.
- Adjusts the file creation and modification dates to match the post date.
- Automatically generates filenames based on post title and date.
- Outputs the progress to the console including the number of found posts and the file being archived.
- The original link to the LiveJournal post is appended to the end of each markdown file.

## Prerequisites:
- Python 3.x

## Usage:

1. **Setup**:
    - Clone this repository to your local machine.
    - Navigate to the directory.
    - Install the required Python packages by running:  
      ```bash
      pip install -r requirements.txt
      ```

2. **Run the Tool**:
    - Execute the script using Python:
      ```bash
      python main.py
      ```

3. **Output**:
    - The markdown files will be saved in the `MD` directory where the `main.py` script is executed.

## Dependencies:

- **BeautifulSoup4**: For HTML parsing.
- **requests**: To make HTTP requests.
- **pywin32**: To modify file creation and modification dates on Windows.

## Contribution:
If you'd like to contribute, please fork the repository and make changes as you'd like. Pull requests are warmly welcome.

## Issues:
If you encounter any issues or have feature requests, please file an issue on the GitHub project. 

## Disclaimer:
Please use this tool responsibly. Making rapid or aggressive requests may lead to IP bans or other restrictions from LiveJournal. Always respect the terms of service of any platform you interact with.

## License:
This project is licensed under the MIT License. 

## Note:
- The script modifies the creation and modification dates of the markdown files to reflect the date of the original LiveJournal post. This way, the file metadata matches the original publishing date of the content.
- This tool is designed for public LiveJournal blogs. It may not work correctly with private or locked posts.

## Acknowledgments:
- Thank you to those who archived LiveJournal, I thought mine was long gone after nearly two decades I wanted a way to back it up that was still readable.
