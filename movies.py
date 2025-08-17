import requests
import os
from collections import defaultdict

# Sabit API yolunu ve temel domain formatını tanımlıyoruz.
BASE_DOMAIN_FORMAT = "https://m.prectv{domain_num}.sbs"
API_PATH = "/api/movie/by/filtres/0/created/0/4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"

def find_all_working_domains(start=45, end=100):
    """
    Belirtilen aralıktaki TÜM çalışan domainleri bulur ve bir liste olarak döndürür.
    """
    working_domains = []
    print(f"🔍 Potansiyel sunucular taranıyor ({start}-{end} aralığında)...")
    for i in range(start, end + 1):
        domain = BASE_DOMAIN_FORMAT.format(domain_num=i)
        try:
            # Sadece domainin çalışıp çalışmadığını kontrol et
            response = requests.get(domain, timeout=5, headers={"user-agent": "okhttp/4.12.0"})
            if response.status_code == 200:
                print(f"  [+] Aktif sunucu adayı bulundu: {domain}")
                working_domains.append(domain)
        except requests.exceptions.RequestException:
            # Bağlantı hatası olanları sessizce geç
            continue
    print(f"✅ Toplam {len(working_domains)} adet aktif sunucu adayı bulundu.")
    return working_domains

def find_server_with_content(domain_list):
    """
    Verilen domain listesini sırayla dener ve içerik (film) barındıran ilk sunucuyu bulur.
    """
    print("\n🔍 İçerik barındıran sunucu aranıyor...")
    if not domain_list:
        return None

    for domain in domain_list:
        # API'nin ilk sayfasını kontrol ederek içerik olup olmadığını anlarız.
        # Sayfa numarasını (created/{page}) URL'den kaldırdık, çünkü API'nin ilk sayfası yeterli.
        test_url = domain + API_PATH
        print(f"  [*] {domain} kontrol ediliyor...")
        try:
            response = requests.get(test_url, timeout=10, headers={"user-agent": "okhttp/4.12.0"})
            if response.status_code == 200:
                data = response.json()
                # Eğer data bir liste ise ve içinde en az bir eleman varsa, bu sunucuda içerik var demektir.
                if isinstance(data, list) and data:
                    print(f"✅ İçerik dolu sunucu bulundu: {domain}")
                    return domain
                else:
                    print(f"  [-] {domain} aktif fakat içerik boş.")
            else:
                print(f"  [-] {domain} aktif fakat API hatası veriyor (HTTP {response.status_code}).")
        except (requests.exceptions.RequestException, ValueError):
            # Bağlantı veya JSON hatası olursa bu sunucuyu atla
            print(f"  [-] {domain} ile iletişim kurulamadı veya yanıt bozuk.")
            continue
            
    print("❌ Maalesef içerik barındıran bir sunucu bulunamadı.")
    return None


def get_all_movies(working_domain):
    """
    Çalışan ve içerik dolu domain üzerinden tüm filmleri sayfa sayfa çeker.
    """
    all_movies = []
    page = 0
    
    # API yolunu sayfa numarası için formatlanabilir hale getiriyoruz.
    paginated_api_path = "/api/movie/by/filtres/0/created/{page}/4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"

    while True:
        url = working_domain + paginated_api_path.format(page=page)
        print(f"📄 Sayfa {page} çekiliyor...")
        try:
            response = requests.get(url, headers={"user-agent": "okhttp/4.12.0"})
            if response.status_code != 200:
                break
            data = response.json()
            if not data:
                print(f"✅ Tüm filmler alındı. Toplam sayfa: {page}")
                break
            all_movies.extend(data)
            page += 1
        except (requests.exceptions.RequestException, ValueError):
            print(f"   - Hata: Sayfa {page} çekilirken bir sorun oluştu.")
            break
    return all_movies

def categorize_movies(movies):
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
    playlist_lines = []
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

def save_to_file(categorized_content, filename="rectv_filmler.m3u"):
    # Dosyanın en başına #EXTM3U etiketini ekliyoruz.
    final_content = "#EXTM3U\n\n"
    
    for category, content in categorized_content.items():
        final_content += f"#Kategori: {category}\n"
        final_content += content + "\n\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_content.strip())
    print(f"📁 M3U dosyası başarıyla kaydedildi: {filename}")

if __name__ == "__main__":
    # 1. Adım: Tüm potansiyel aktif sunucuları bul
    active_domains = find_all_working_domains()

    # 2. Adım: Aktif sunucular arasından içerik barındıranı bul
    content_server = find_server_with_content(active_domains)

    if not content_server:
        print("🔴 İşlem durduruldu. İçerik dolu bir sunucu bulunamadı.")
    else:
        # 3. Adım: İçerik dolu sunucudan tüm filmleri çek
        movies = get_all_movies(content_server)
        print(f"\n🎬 Toplam {len(movies)} film bulundu.")

        if movies:
            # 4. Adım: Filmleri kategorize et
            categorized_movies = categorize_movies(movies)
            
            # 5. Adım: Her kategori için M3U içeriğini oluştur
            m3u_by_category = {}
            for category, movies_in_category in categorized_movies.items():
                m3u_by_category[category] = extract_movie_links(movies_in_category, category)
            
            # 6. Adım: Oluşturulan içerikleri dosyaya kaydet
            save_to_file(m3u_by_category)