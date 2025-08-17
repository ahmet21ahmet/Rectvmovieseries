import requests
import os
from collections import defaultdict

# --- AYARLAR ---
# Taranacak domain numara aralığı
DOMAIN_START = 45
DOMAIN_END = 100
# Çıktı dosyasının adı
OUTPUT_FILENAME = "rectv_filmler_guncel.m3u"
# Kullanılacak User-Agent
USER_AGENT = "okhttp/4.12.0"

# --- SABİTLER ---
BASE_DOMAIN_FORMAT = "https://m.prectv{domain_num}.sbs"
API_PATH_FORMAT = "/api/movie/by/filtres/0/created/{page}/4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"

def process_movies_for_links(movie_list):
    """
    Verilen bir film listesini işler ve içindeki geçerli .m3u8 linklerini
    M3U formatında bir metin listesine dönüştürür.
    Ayrıca kaç adet geçerli link bulunduğunu da döndürür.
    """
    playlist_lines = []
    valid_links_found = 0

    for movie in movie_list:
        sources = movie.get("sources", [])
        for source in sources:
            url = source.get("url")
            if url and url.endswith(".m3u8"):
                # Bu filmde en az bir geçerli link bulduk.
                valid_links_found += 1
                
                title = movie.get("title", "Bilinmeyen Film")
                logo = movie.get("image", "")
                movie_id = str(movie.get("id", ""))
                year = movie.get("year", "Tarih Yok")
                
                # Kategoriyi genres listesinden alıyoruz
                genres = movie.get("genres", [])
                category = genres[0].get("title", "Diğer") if genres else "Diğer"
                
                # Proxy URL'sini oluştur
                proxy_url = f"https://1.nejyoner19.workers.dev/?url={url}"
                quality = source.get("quality", "")
                quality_str = f" [{quality}]" if quality else ""
                
                entry = [
                    f'#EXTINF:-1 tvg-id="{movie_id}" tvg-logo="{logo}" group-title="{category}",{title} ({year}){quality_str}',
                    f'#EXTVLCOPT:http-user-agent={USER_AGENT}',
                    f'#EXTVLCOPT:http-referrer=https://twitter.com',
                    proxy_url
                ]
                playlist_lines.extend(entry)
                # Bir film için birden fazla kaynak varsa sadece ilkini almak için döngüden çıkabiliriz.
                # Eğer tüm kaynakları (720p, 1080p vb.) istiyorsak bu 'break' satırını kaldır.
                break 
                
    return playlist_lines, valid_links_found

def find_best_server_and_fetch_all_movies():
    """
    Domain aralığını tarar. Sadece aktif değil, aynı zamanda İŞE YARAR (.m3u8 linki içeren)
    içerik sunan ilk sunucuyu bulur ve o sunucudaki TÜM filmleri çeker.
    """
    print(f"🚀 Betik başlatıldı. Sunucular taranıyor ({DOMAIN_START}-{DOMAIN_END})...")
    
    for i in range(DOMAIN_START, DOMAIN_END + 1):
        domain = BASE_DOMAIN_FORMAT.format(domain_num=i)
        test_url = domain + API_PATH_FORMAT.format(page=0)
        
        print(f"\n[*] Deneniyor: {domain}")
        
        try:
            response = requests.get(test_url, timeout=10, headers={"user-agent": USER_AGENT})
            
            if response.status_code == 200:
                movies_page_0 = response.json()
                
                # Sunucu aktif, şimdi içinde işe yarar veri var mı kontrol edelim.
                if isinstance(movies_page_0, list) and movies_page_0:
                    _, link_count = process_movies_for_links(movies_page_0)
                    
                    if link_count > 0:
                        print(f"✅ BAŞARILI! Bu sunucuda {link_count} adet kullanılabilir link bulundu: {domain}")
                        print("    Bu sunucudaki tüm filmler çekiliyor...")
                        
                        # Harika! İşe yarar bir sunucu bulduk. Şimdi tüm sayfaları buradan çekelim.
                        all_movies = movies_page_0
                        page = 1
                        while True:
                            next_page_url = domain + API_PATH_FORMAT.format(page=page)
                            print(f"    - Sayfa {page} çekiliyor...")
                            try:
                                r = requests.get(next_page_url, headers={"user-agent": USER_AGENT})
                                if r.status_code != 200: break
                                data = r.json()
                                if not data: break # Sayfada veri yoksa döngüyü bitir.
                                all_movies.extend(data)
                                page += 1
                            except:
                                break # Herhangi bir hatada o sayfayı atla ve döngüyü bitir.
                        
                        return all_movies # Tüm filmleri içeren listeyi döndür ve aramayı bitir.
                    else:
                        print(f"  [-] Sunucu aktif ama ilk sayfasında kullanılabilir .m3u8 linki bulunamadı.")
                else:
                    print(f"  [-] Sunucu aktif ama içerik listesi boş.")
            else:
                 print(f"  [-] Sunucu yanıt vermiyor (HTTP {response.status_code}).")

        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"  [-] Sunucuya bağlanılamadı veya yanıt bozuk. Hata: {e.__class__.__name__}")
            
    # Eğer döngü biterse ve hiçbir şey döndürülmezse, sunucu bulunamamıştır.
    return None

def save_playlist(all_movies, filename):
    """
    Tüm film listesini işler ve tek bir M3U dosyasına kaydeder.
    """
    if not all_movies:
        print("❌ Kaydedilecek film bulunamadı.")
        return

    print("\n M3U dosyası oluşturuluyor...")
    
    # Filmleri kategorilere ayıralım
    categorized_movies = defaultdict(list)
    for movie in all_movies:
        genres = movie.get("genres", [])
        category = genres[0].get("title", "Diğer") if genres else "Diğer"
        categorized_movies[category].append(movie)

    # Dosya içeriğini oluşturalım
    final_playlist_content = ["#EXTM3U"]
    
    # Kategorileri alfabetik olarak sıralayarak dosyaya yazalım
    for category in sorted(categorized_movies.keys()):
        movies_in_category = categorized_movies[category]
        m3u_lines, _ = process_movies_for_links(movies_in_category)
        if m3u_lines: # Sadece içinde link olan kategorileri ekle
            final_playlist_content.extend(m3u_lines)

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(final_playlist_content))
        
    print(f"\n📁 M3U dosyası başarıyla kaydedildi: {filename}")


if __name__ == "__main__":
    # 1. Adım: İşe yarar içeriği olan en iyi sunucuyu bul ve tüm filmleri çek
    final_movie_list = find_best_server_and_fetch_all_movies()
    
    if final_movie_list:
        print(f"\n🎬 Toplam {len(final_movie_list)} film verisi işlenmek üzere çekildi.")
        # 2. Adım: Çekilen tüm filmleri işle ve dosyaya kaydet
        save_playlist(final_movie_list, OUTPUT_FILENAME)
    else:
        print("\n🔴 Maalesef kullanılabilir içerik sunan hiçbir sunucu bulunamadı.")