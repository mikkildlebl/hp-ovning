from PIL import Image
import io, base64
img = Image.open(r'C:\Users\Mikael\Desktop\hp_images\2023-03-25_provpass-2-kvant_p6.png')
w, h = img.size
crop = img.crop((0, int(h * 0.45), w, h))
max_w = 600
ratio = max_w / crop.width
crop = crop.resize((max_w, int(crop.height * ratio)), Image.LANCZOS)
buf = io.BytesIO()
crop.save(buf, format='JPEG', quality=75)
data = base64.b64encode(buf.getvalue()).decode()
with open(r'C:\Users\Mikael\Desktop\b64_cropped.txt', 'w') as f:
    f.write(data)
print("done", len(data))
