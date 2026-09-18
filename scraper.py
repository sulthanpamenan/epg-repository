import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json
import os

async def scrape_tivie():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        print("Accessing tivie.id...")
        
        try:
            await page.goto("https://tivie.id/channel/antv/besok", timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(7000)
            
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            schedule_list = []
            items = soup.select('.schedule-item, .list-group-item, tr') 
            
            for item in items:
                text = item.get_text(strip=True)
                if text:
                    schedule_list.append(text)
            
            output_data = {
                "status": "success",
                "total_data": len(schedule_list),
                "schedules": schedule_list
            }
            
            os.makedirs("output", exist_ok=True)
            with open("output/schedule.json", "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
                
            print(f"Successfully retrieved {len(schedule_list)} schedule records!")

        except Exception as e:
            print(f"Scraping failed: {e}")
            raise e
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_tivie())
