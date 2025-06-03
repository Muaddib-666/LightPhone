This Python script will take a collection of local music files and compiles them into a single track with options for encoding quality and creating a gapless playback. Folders with separate artists or individual albums can be imported and as the audio compiles, album artwork and facts about the album/band are shown (if available).

Download both the .bat and .py files into the same folder. Double click the .bat and that will run the Python script.

If you have album artwork or other non-music files in your folder structure, the CMD window will output some text saying something like "Skipping C:/Users/.../Music_test\Artist\Album\folder.jpg: list index out of range". This can be ignored as it is saying that the file type won't be included in the compliation. There is no impact on the final MP3 file.

This code has been tested on Windows, but not on Mac. 

Screenshot:
![Screenshot 2025-06-03 124322](https://github.com/user-attachments/assets/ba3f2d6e-304d-471c-b48b-bc61142cd137)
