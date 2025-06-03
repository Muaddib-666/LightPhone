This Python script will take a collection of local music files and compile them into a single track with options for encoding quality and creating a gapless playback. Folders with separate artists or even individual albums can be loaded in. As the audio compiles, album artwork and facts about the band are shown (if available). If album artwork isn't available, you'll see a grey box instead.

Download both the .bat and .py files into the same folder. Double click the .bat and that will run the Python script.

If you have album artwork or other non-music files in your folder structure, the CMD will output some text saying something similar to "Skipping C:/Users/.../Music_test\Artist\Album\folder.jpg: list index out of range". This is just saying that the file type won't be included in the compliation and it can be ignored.

This code has been tested on Windows, but not on Mac. 

Screenshot:
![Screenshot 2025-06-03 124322](https://github.com/user-attachments/assets/ba3f2d6e-304d-471c-b48b-bc61142cd137)
