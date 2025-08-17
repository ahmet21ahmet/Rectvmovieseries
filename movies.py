import requests
import os
import json
from collections import defaultdict

# --- AYARLAR ---
# Taranacak domain numara aralığı
DOMAIN_START = 45
DOMAIN_END = 100
# Çıktı dosyasının adı
OUTPUT_FILENAME = "rectv_filmler_son_hali.m3u"
# Kullanılacak User-Agent
USER_AGENT = "okhttp/4.12.0"
# İstekler için zaman aşımı süresi (saniye)
TIMEOUT = 15

# --- SABİTLER ---
BASE_DOMAIN_FORMAT = "https://m.prectv{domain_num}.lol"
API_PATH_FORMAT = "/api/movie/by/filtres/0/created/{page}/4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"

def find_best_server():
    """
    Domain aralığını tarar. Sadece aktif değil, aynı zamanda İŞE YARAR (.m3u8 linki içeren)
    içerik sunan ilk sunucuyu bulur ve o sunucunun adresini döndürür.
    """
    print(f"🚀 Betik başlatıldı. Sunucular taranıyor ({DOMAIN_START}-{DOMAIN_END})...")
    
    for i in range(DOMAIN_START, DOMAIN_END + 1):
        domain = BASE_DOMAIN_FORMAT.format(domain_num=i)
        test_url = domain + API_PATH_FORMAT.format(page=0)
        
        print(f"\n[*] Deneniyor: {domain}")
        
        try:
            response = requests.get(test_url, timeout=TIMEOUT, headers={"user-agent": USER_AGENT})
            
            if response.status_code == 200:
                print(f"  [+] Sunucu aktif (HTTP 200). İçerik kontrol ediliyor...")
                movies_page_0 = response.json()
                
                if isinstance(movies_page_0, list) and movies_page_0:
                    print(f"  [+] Sunucuda {len(movies_page_0)} adet film verisi bulundu.")
                    
                    # HATA AYIKLAMA: Sunucudan gelen ilk filmin ham verisini yazdır.
                    # Bu, veri yapısını kontrol etmemizi sağlar.
                    print("--- İlk Filmin Ham Verisi (Hata Ayıklama) ---")
                    print(json.dumps(movies_page_0[0], indent=2, ensure_ascii=False))
                    print("---------------------------------------------")

                    # Şimdi bu filmlerin içinde geçerli link var mı diye kontrol edelim.
                    for movie in movies_page_0:
                        sources = movie.get("sources", [])
                        if sources and isinstance(sources, list):
                            for source in sources:
                                url = source.get("url")
                                if url and isinstance(url, str) and url.endswith(".m3u8"):
                                    print(f"✅ BAŞARILI! Kullanılabilir .m3u8 linki bulundu.")
                                    print(f"🏆 En iyi sunucu olarak seçildi: {domain}")
                                    return domain # En iyi sunucuyu bulduk, adresi döndür ve aramayı bitir.
                    
                    print(f"  [-] Sunucu aktif ve film listesi dolu, ancak listede geçerli .m3u8 linki bulunamadı.")
                else:
                    print(f"  [-] Sunucu aktif ama içerik listesi boş veya formatı bozuk.")
            else:
                 print(f"  [-] Sunucu yanıt vermiyor (HTTP {response.status_code}).")

        except requests.exceptions.Timeout:
            print(f"  [-] Sunucuya bağlanırken zaman aşımına uğradı.")
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"  [-] Sunucuya bağlanılamadı veya yanıt bozuk. Hata: {e.__class__.__name__}")
            
    return None

def fetch_all_movies_from_server(best_server):
    """
    En iyi olarak seçilen sunucudan tüm filmleri sayfa sayfa çeker.
    """
    if not best_server:
        return []
        
    print(f"\n Bütün filmler {best_server} adresinden çekiliyor...")
    all_movies = []
    page = 0
    while True:
        url = best_server + API_PATH_FORMAT.format(page=page)
        print(f"    - Sayfa {page} çekiliyor...")
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"user-agent": USER_AGENT})
            if r.status_code != 200:
                print(f"    - Sayfa {page} alınamadı (HTTP {r.status_code}), işlem tamamlandı.")
                break
            data = r.json()
            if not data or not isinstance(data, list):
                print("    - Son sayfaya ulaşıldı, işlem tamamlandı.")
                break
            all_movies.extend(data)
            page += 1
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            print(f"    - Sayfa {page} çekilirken hata oluştu, işlem tamamlandı.")
            break
    return all_movies

def create_m3u_file(movie_list, filename):
    """
    Verilen film listesinden geçerli linkleri ayıklar ve M3U dosyası oluşturur.
    """
    print("\n M3U dosyası oluşturuluyor...")
    
    playlist_content = ["#EXTM3U"]
    links_found = 0

    for movie in movie_list:
        sources = movie.get("sources", [])
        if not sources or not isinstance(sources, list):
            continue

        for source in sources:
            url = source.get("url")
            if url and isinstance(url, str) and url.endswith(".m3u8"):
                links_found += 1
                
                title = movie.get("title", "Bilinmeyen Film")
                logo = movie.get("image", "")
                movie_id = str(movie.get("id", ""))
                year = movie.get("year", "Tarih Yok")
                genres = movie.get("genres", [])
                category = genres[0].get("title", "Diğer") if genres else "Diğer"
                proxy_url = f"https://1.nejyoner19.workers.dev/?url={url}"
                quality = source.get("quality", "")
                quality_str = f" [{quality}]" if quality else ""
                
                playlist_content.append(f'#EXTINF:-1 tvg-id="{movie_id}" tvg-logo="{logo}" group-title="{category}",{title} ({year}){quality_str}')
                playlist_content.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
                playlist_content.append(f'#EXTVLCOPT:http-referrer=https://twitter.com')
                playlist_content.append(proxy_url)

    if links_found > 0:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(playlist_content))
        print(f"\n📁 Başarılı! Toplam {links_found} link içeren M3U dosyası kaydedildi: {filename}")
    else:
        print("\n❌ Maalesef, çekilen filmlerin hiçbirinde geçerli .m3u8 linki bulunamadı. Dosya oluşturulmadı.")

if __name__ == "__main__":
    # 1. Adım: İşe yarar içeriği olan en iyi sunucuyu bul
    best_server_domain = find_best_server()
    
    if best_server_domain:
        # 2. Adım: O sunucudaki tüm filmleri çek
        final_movie_list = fetch_all_movies_from_server(best_server_domain)
        
        if final_movie_list:
            print(f"\n🎬 Toplam {len(final_movie_list)} film verisi işlenmek üzere çekildi.")
            # 3. Adım: Çekilen tüm filmleri işle ve dosyaya kaydet
            create_m3u_file(final_movie_list, OUTPUT_FILENAME)
        else:
            print("\n🔴 Sunucu bulundu ama film listesi çekilemedi.")
    else:
        print("\n🔴 Maalesef kullanılabilir içerik sunan hiçbir sunucu bulunamadı.")