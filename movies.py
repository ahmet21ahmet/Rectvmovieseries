import requests
import os
from collections import defaultdict

# Sabit API yolunu ve temel domain formatını tanımlıyoruz.
# Değişen kısım {domain_num} ile belirtilmiştir.
BASE_DOMAIN_FORMAT = "https://m.prectv{domain_num}.sbs"
API_PATH = "/api/movie/by/filtres/0/created/{page}/4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"

def find_working_domain(start=45, end=100):
    """
    Belirtilen sayı aralığında çalışan bir domain bulmaya çalışır.
    Örn: m.prectv45.sbs, m.prectv46.sbs, ...
    """
    print(f"🔍 Çalışan domain aranıyor ({start}-{end} aralığında)...")
    for i in range(start, end + 1):
        domain = BASE_DOMAIN_FORMAT.format(domain_num=i)
        try:
            # Domainin çalışıp çalışmadığını anlamak için ana sayfasına bir istek atıyoruz.
            # timeout=5, isteğin 5 saniyeden uzun sürmesi durumunda vazgeçmesini sağlar.
            response = requests.get(domain, timeout=5, headers={"user-agent": "okhttp/4.12.0"})
            # HTTP 200 OK durum kodu, sayfanın başarılı bir şekilde yüklendiğini gösterir.
            if response.status_code == 200:
                print(f"✅ Çalışan domain bulundu: {domain}")
                return domain
        except requests.exceptions.RequestException as e:
            # Bağlantı hatası, zaman aşımı gibi durumlarda bir sonraki domaini dene.
            print(f"   - {domain} çalışmıyor. ({e.__class__.__name__})")
            continue
    print("❌ Çalışan bir domain bulunamadı.")
    return None

def get_all_movies(working_domain):
    """
    Çalışan domain üzerinden tüm filmleri sayfa sayfa çeker.
    """
    all_movies = []
    page = 0

    while True:
        # Tam API URL'sini çalışan domain ve sayfa numarası ile oluşturuyoruz.
        url = working_domain + API_PATH.format(page=page)
        print(f"📄 Sayfa {page} çekiliyor...")
        try:
            response = requests.get(url, headers={"user-agent": "okhttp/4.12.0"})

            if response.status_code != 200:
                print(f"   - Hata: Sunucudan HTTP {response.status_code} kodu alındı.")
                break

            data = response.json()
            # Eğer sunucudan boş bir liste gelirse, filmlerin sonuna gelmişiz demektir.
            if not data:
                print(f"✅ Tüm filmler alındı. Toplam sayfa: {page}")
                break

            all_movies.extend(data)
            page += 1
        except requests.exceptions.RequestException as e:
            print(f"   - Hata: Veri çekilirken bir bağlantı hatası oluştu: {e}")
            break
        except ValueError: # JSON çözme hatası
            print(f"   - Hata: Sunucudan gelen yanıt JSON formatında değil.")
            break

    return all_movies

def categorize_movies(movies):
    """
    Filmleri türlerine (genres) göre kategorilere ayırır.
    """
    categorized_movies = defaultdict(list)
    for movie in movies:
        genres = movie.get("genres", [])
        if not genres:
            categorized_movies["Diğer"].append(movie)
            continue
        for genre in genres:
            category = genre.get("title", "Diğer")
            categorized_movies[category].append(movie)
    return categorized_movies

def extract_movie_links(movies, category):
    """
    Belirli bir kategorideki filmler için M3U formatında metin oluşturur.
    """
    playlist_lines = [
        f'#EXTM3U',
        f'#Kategori: {category}',
        f'#Bu kategoride {category.lower()} türündeki filmler yer almaktadır.\n'
    ]

    for movie in movies:
        title = movie.get("title", "Bilinmeyen Film")
        logo = movie.get("image", "")
        movie_id = str(movie.get("id", ""))
        sources = movie.get("sources", [])
        year = movie.get("year", "Tarih Yok")
        group = category

        for source in sources:
            url = source.get("url")
            if url and url.endswith(".m3u8"):
                # URL'yi proxy formatına dönüştürüyoruz
                url = f"https://1.nejyoner19.workers.dev/?url={url}"
                quality = source.get("quality", "")
                quality_str = f" [{quality}]" if quality else ""
                entry = [
                    f'#EXTINF:-1 tvg-id="{movie_id}" tvg-logo="{logo}" group-title="{group}",{title} ({year}){quality_str}',
                    '#EXTVLCOPT:http-user-agent=okhttp/4.12.0',
                    '#EXTVLCOPT:http-referrer=https://twitter.com',
                    url
                ]
                playlist_lines.extend(entry)
    return '\n'.join(playlist_lines)

def save_to_file(content, filename="rectv_filmler.m3u"):
    """
    Oluşturulan içeriği belirtilen dosyaya kaydeder.
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"📁 M3U dosyası başarıyla kaydedildi: {filename}")

if __name__ == "__main__":
    # 1. Adım: Çalışan domaini bul (artık 45-100 aralığında arayacak)
    domain = find_working_domain()

    # Eğer domain bulunamazsa betiği sonlandır
    if not domain:
        print("🔴 İşlem durduruldu.")
    else:
        # 2. Adım: Tüm filmleri çek
        movies = get_all_movies(domain)
        print(f"🎬 Toplam {len(movies)} film bulundu.")

        if movies:
            # 3. Adım: Filmleri kategorize et
            categorized_movies = categorize_movies(movies)
            
            # 4. Adım: Tüm kategorileri tek bir dosyaya yazmak için birleştir
            all_content_lines = []
            for category, movies_in_category in categorized_movies.items():
                m3u_content = extract_movie_links(movies_in_category, category)
                all_content_lines.append(m3u_content)
            
            # 5. Adım: Dosyaya kaydet
            final_content = "\n\n".join(all_content_lines)
            save_to_file(final_content)