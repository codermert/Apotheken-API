#!/usr/bin/env python3

from flask import Flask, request, jsonify
from crawler import filter_network_packet
import json
import requests
from datetime import datetime

app = Flask(__name__)

def get_pharmacies_by_coordinates(latitude, longitude, radius=25, date_filter=None):
    """Koordinata göre eczane arama - orijinal API ile uyumlu"""
    print(f"🔍 {latitude}, {longitude} koordinatları için eczane bilgileri çekiliyor...")
    
    # Sabit token
    TOKEN = "216823d96ea25c051509d935955c130fbc72680fc1d3040fe3e8ca0e25f9cd02"
    
    # Tarihi formatla - eğer belirtilmemişse bugünü kullan
    if not date_filter:
        date_filter = datetime.now().strftime("%d.%m.%Y")
    
    # API URL'sini gerçek format ile oluştur
    url = (
        "https://www.aponet.de/apotheke/notdienstsuche"
        f"?tx_aponetpharmacy_search[action]=result"
        f"&tx_aponetpharmacy_search[controller]=Search"
        f"&tx_aponetpharmacy_search[search][plzort]={latitude}%2C+{longitude}"
        f"&tx_aponetpharmacy_search[search][date]={date_filter}"
        f"&tx_aponetpharmacy_search[search][street]=+"
        f"&tx_aponetpharmacy_search[search][radius]={radius}"
        f"&tx_aponetpharmacy_search[search][lat]="
        f"&tx_aponetpharmacy_search[search][lng]="
        f"&tx_aponetpharmacy_search[token]={TOKEN}"
        f"&type=1981"
    )
    
    # Tarayıcı gibi headers ekle
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        'Referer': 'https://www.aponet.de/apotheke/notdienstsuche',
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache'
    }
    
    try:
        session = requests.Session()
        session.headers.update(headers)
        
        print(f"📡 İstek URL: {url}")
        res = session.get(url, timeout=15)
        
        if res and res.status_code == 200:
            try:
                data = res.json()
                
                # Debug için JSON kaydet
                debug_file = f'debug_koordinat_{latitude}_{longitude}_{date_filter.replace(".", "_")}.json'
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"🔍 Debug dosyası kaydedildi: {debug_file}")
                
                # Eczane verilerini çıkar - tam uyumlu format
                pharmacies = []
                if 'results' in data and 'apotheken' in data['results'] and 'apotheke' in data['results']['apotheken']:
                    raw_pharmacies = data['results']['apotheken']['apotheke']
                    print(f"📋 Ham veri: {len(raw_pharmacies)} eczane bulundu")
                    
                    for pharmacy in raw_pharmacies:
                        # Basitleştirilmiş format - sadece gerekli alanlar
                        pharmacy_data = {
                            'eczaneAdi': pharmacy.get('name', ''),
                            'adres': f"{pharmacy.get('strasse', '')}, {pharmacy.get('plz', '')} {pharmacy.get('ort', '')}",
                            'telefon': pharmacy.get('telefon', ''),
                            'enlem': pharmacy.get('latitude', ''),
                            'boylam': pharmacy.get('longitude', ''),
                            'mesafe': f"{float(pharmacy.get('distanz', 0)):.1f} km"
                        }
                        
                        # Mesafe kontrolü - sadece belirli mesafe içindeki eczaneleri al
                        try:
                            distance = float(pharmacy.get('distanz', 999))
                            if distance <= radius:
                                pharmacies.append(pharmacy_data)
                        except (ValueError, TypeError):
                            # Mesafe bilgisi yoksa veya geçersizse ekle
                            pharmacies.append(pharmacy_data)
                    
                    # Mesafeye göre sırala
                    pharmacies.sort(key=lambda x: float(x.get('mesafe', '999').replace(' km', '')))
                    
                    print(f"✅ Filtreleme sonrası: {len(pharmacies)} eczane")
                    return pharmacies
                else:
                    print("⚠️ Veri yapısı beklenen formatta değil")
                    print(f"🔍 Gelen veri yapısı: {list(data.keys()) if data else 'Boş'}")
                    return []
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse hatası: {str(e)}")
                print(f"📄 Ham yanıt: {res.text[:500]}...")
                return []
        else:
            print(f"❌ İstek başarısız oldu. Durum kodu: {res.status_code if res else 'Yanıt yok'}")
            if res:
                print(f"📄 Hata yanıtı: {res.text[:200]}...")
            return []
            
    except Exception as e:
        print(f"❌ Genel hata: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

@app.route('/')
def search_pharmacies():
    """API endpoint: koordinata göre eczane arama - orijinal API formatında"""
    try:
        # URL parametrelerini al
        lat = request.args.get('enlem', type=float)
        lng = request.args.get('boylam', type=float)
        rad = request.args.get('yaricap', default=25, type=float)
        date_param = request.args.get('tarih')  # İsteğe bağlı tarih parametresi

        if not lat or not lng:
            return jsonify({
                "hata": "Enlem ve boylam parametreleri gerekli",
                "örnek": "/?enlem=51.209228338620505&boylam=6.74871264670858&yaricap=5&tarih=02.08.2025"
            }), 400

        # Eczaneleri ara
        pharmacies = get_pharmacies_by_coordinates(lat, lng, rad, date_param)
        
        # Basit format döndür
        response_data = {
            "durum": "başarılı" if pharmacies else "veri bulunamadı",
            "parametreler": {
                "enlem": lat,
                "boylam": lng,
                "yaricap": rad,
                "tarih": date_param
            },
            "eczaneSayisi": len(pharmacies),
            "eczaneler": pharmacies
        }
        
        return jsonify(response_data)

    except ValueError as e:
        return jsonify({
            "hata": "Geçersiz koordinat değeri",
            "mesaj": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "hata": "Sunucu hatası",
            "mesaj": str(e)
        }), 500

@app.route('/original-format')
def search_pharmacies_original():
    """Orijinal API ile birebir aynı format"""
    try:
        lat = request.args.get('enlem', type=float)
        lng = request.args.get('boylam', type=float)
        rad = request.args.get('yaricap', default=5, type=float)  # Varsayılan 5 km
        date_param = request.args.get('tarih')

        if not lat or not lng:
            return jsonify({
                "hata": "Enlem ve boylam parametreleri gerekli"
            }), 400

        result = get_pharmacies_by_coordinates(lat, lng, rad, date_param)
        
        # Orijinal API formatı için veriyi yeniden yapılandır
        original_format_data = []
        for pharmacy in result:
            original_format_data.append({
                'name': pharmacy.get('eczaneAdi', ''),
                'strasse': pharmacy.get('adres', '').split(',')[0] if ',' in pharmacy.get('adres', '') else '',
                'plz': pharmacy.get('adres', '').split(',')[1].strip().split()[0] if ',' in pharmacy.get('adres', '') else '',
                'ort': ' '.join(pharmacy.get('adres', '').split(',')[1].strip().split()[1:]) if ',' in pharmacy.get('adres', '') else '',
                'telefon': pharmacy.get('telefon', ''),
                'latitude': pharmacy.get('enlem', ''),
                'longitude': pharmacy.get('boylam', ''),
                'distanz': pharmacy.get('mesafe', '').replace(' km', '')
            })
        
        # Sadece results kısmını döndür (orijinal API gibi)
        return jsonify({
            "results": {
                "apotheken": {
                    "apotheke": original_format_data
                }
            }
        })

    except Exception as e:
        return jsonify({
            "hata": str(e)
        }), 500

if __name__ == "__main__":
    print("🏥 Eczane API Servisi - Orijinal Uyumlu Versiyon")
    print("=" * 60)
    print("📍 Ana endpoint: http://localhost:5000/?enlem=51.209228338620505&boylam=6.74871264670858&yaricap=5")
    print("📍 Orijinal format: http://localhost:5000/original-format?enlem=51.209228338620505&boylam=6.74871264670858&yaricap=5")
    print("📅 Tarih parametresi: &tarih=02.08.2025")
    app.run(debug=True)