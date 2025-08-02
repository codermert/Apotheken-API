from flask import Flask, request, jsonify
import json
import requests
from datetime import datetime
import os
import traceback

app = Flask(__name__)

def get_pharmacies_by_coordinates(latitude, longitude, radius=25, date_filter=None):
    """Koordinata göre eczane arama - Vercel uyumlu"""
    try:
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
        
        # HTTP isteği gönder
        session = requests.Session()
        session.headers.update(headers)
        
        print(f"📡 İstek gönderiliyor...")
        response = session.get(url, timeout=10)
        
        if response and response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ JSON verisi alındı")
                
                # Eczane verilerini çıkar
                pharmacies = []
                if (data and 
                    isinstance(data, dict) and 
                    'results' in data and 
                    'apotheken' in data['results'] and 
                    'apotheke' in data['results']['apotheken']):
                    
                    raw_pharmacies = data['results']['apotheken']['apotheke']
                    print(f"📋 {len(raw_pharmacies)} eczane bulundu")
                    
                    for pharmacy in raw_pharmacies:
                        try:
                            # Güvenli veri çıkarma
                            name = str(pharmacy.get('name', ''))
                            strasse = str(pharmacy.get('strasse', ''))
                            plz = str(pharmacy.get('plz', ''))
                            ort = str(pharmacy.get('ort', ''))
                            telefon = str(pharmacy.get('telefon', ''))
                            latitude_str = str(pharmacy.get('latitude', ''))
                            longitude_str = str(pharmacy.get('longitude', ''))
                            distanz_str = str(pharmacy.get('distanz', '0'))
                            
                            # Mesafe kontrolü
                            try:
                                distance = float(distanz_str)
                                if distance > radius:
                                    continue
                            except (ValueError, TypeError):
                                distance = 0
                            
                            # Eczane verisini oluştur
                            pharmacy_data = {
                                'eczaneAdi': name,
                                'adres': f"{strasse}, {plz} {ort}".strip(),
                                'telefon': telefon,
                                'enlem': latitude_str,
                                'boylam': longitude_str,
                                'mesafe': f"{distance:.1f} km"
                            }
                            
                            pharmacies.append(pharmacy_data)
                            
                        except Exception as e:
                            print(f"⚠️ Eczane verisi işlenirken hata: {str(e)}")
                            continue
                    
                    # Mesafeye göre sırala
                    try:
                        pharmacies.sort(key=lambda x: float(x.get('mesafe', '999').replace(' km', '')))
                    except:
                        pass
                    
                    print(f"✅ {len(pharmacies)} eczane işlendi")
                    return pharmacies
                else:
                    print("⚠️ Beklenen veri yapısı bulunamadı")
                    return []
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse hatası: {str(e)}")
                return []
        else:
            print(f"❌ HTTP hatası: {response.status_code if response else 'Yanıt yok'}")
            return []
            
    except requests.RequestException as e:
        print(f"❌ İstek hatası: {str(e)}")
        return []
    except Exception as e:
        print(f"❌ Genel hata: {str(e)}")
        traceback.print_exc()
        return []

@app.route('/')
def search_pharmacies():
    """Ana API endpoint"""
    try:
        # Parametreleri al
        lat = request.args.get('enlem')
        lng = request.args.get('boylam')
        rad = request.args.get('yaricap', '25')
        date_param = request.args.get('tarih')
        
        # Parametre kontrolü
        if not lat or not lng:
            return jsonify({
                "hata": "Enlem ve boylam parametreleri gerekli",
                "örnek": "/?enlem=50.9785762&boylam=10.2914262&yaricap=10",
                "api_durumu": "çalışıyor"
            }), 400
        
        # Tür dönüşümü
        try:
            lat_float = float(lat)
            lng_float = float(lng)
            rad_float = float(rad)
        except (ValueError, TypeError):
            return jsonify({
                "hata": "Geçersiz koordinat değerleri",
                "mesaj": "Enlem, boylam ve yarıçap sayısal değer olmalı"
            }), 400
        
        # Eczaneleri ara
        print(f"🔍 Arama başlıyor: {lat_float}, {lng_float}")
        pharmacies = get_pharmacies_by_coordinates(lat_float, lng_float, rad_float, date_param)
        
        # Sonuç döndür
        response_data = {
            "durum": "başarılı" if pharmacies else "veri bulunamadı",
            "parametreler": {
                "enlem": lat_float,
                "boylam": lng_float,
                "yaricap": rad_float,
                "tarih": date_param
            },
            "eczaneSayisi": len(pharmacies),
            "eczaneler": pharmacies
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Endpoint hatası: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "hata": "Sunucu hatası",
            "mesaj": str(e),
            "durum": "hata"
        }), 500

@app.route('/health')
def health_check():
    """Sağlık kontrolü"""
    return jsonify({
        "status": "healthy",
        "service": "Eczane API",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1-vercel"
    })

@app.route('/test')
def test_endpoint():
    """Test endpoint'i"""
    return jsonify({
        "message": "API çalışıyor!",
        "test_url": "/?enlem=50.9785762&boylam=10.2914262&yaricap=10",
        "timestamp": datetime.now().isoformat()
    })

# Vercel için handler
def handler(request):
    return app(request.environ, lambda s, h: None)

# Local test için
if __name__ == "__main__":
    app.run(debug=True)
