This Python script will take a collection of local music files and compile them into a single track with options for encoding quality and creating a gapless playback. As the audio compiles, album artwork and facts about the band are shown (if available). If album artwork isn't available, you'll see a grey box instead.

This code has been tested on Windows, but not on Mac. Download both the .bat and .py files into the same folder. Then you can just run the .bat file instead of opening a CMD window and navigating to the python file.

If you have album artwork or other non-music files in your folder structure, the CMD will output some text saying something similar to this "Skipping C:/Users/.../Music_test\Battles\Mirrored\folder.jpg: list index out of range". This is just saying that the file type won't be included in the compliation and it can be ignored.

Screenshot:

