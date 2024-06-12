import scrapy
from playwright.async_api import async_playwright
import time
import re
import asyncio

class ScrapperClubSpider(scrapy.Spider):
    name = "scrapper-club"
    allowed_domains = ["bartonassociates.com"]
    # start_urls = ["https://weatherbyhealthcare.com/locum-tenens-physician-jobs"]

    def start_requests(self):
        url = "https://www.amnhealthcare.com/jobs/c/Physician/"
        yield scrapy.Request(url, meta={"playwright": True})

    async def parse(self, response):
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(response.url)
                await page.wait_for_load_state("domcontentloaded")
            except Exception as e:
                print(f"An error occurred: {e}")
            locations = await self.extract_options(page, 'location')
            for count, location in enumerate(locations):
                try:
                    await page.click("#multi-locations",timeout=60000)
                    await page.wait_for_timeout(80000)

                    if count > 0:
                        pre_for_loc_value = f"d-{locations[count - 1].lower()}"
                        await page.click(f'label[for="{pre_for_loc_value}"]')
                        await page.wait_for_timeout(15000)

                    for_loc_value = f"d-{location.lower()}"
                    await page.click(f'label[for="{for_loc_value}"]')
                    await page.wait_for_timeout(20000)
                    jobs = await page.query_selector(".showing-jobs")
                    if jobs:
                        show_jobs = await jobs.inner_text()
                        has_more = self.extract_and_check_same(show_jobs)
                        if has_more:
                            await self.scroll_to_bottom_and_load_all_content(page)
                            more_jobs = await page.query_selector(".showing-jobs")
                            print(location, await more_jobs.inner_text())
                        else:
                            print(location, await jobs.inner_text())
                        locum_list = await page.query_selector_all('h4.amaranth.card-title')
                        for locum in locum_list:
                            await locum.click()
                            await page.wait_for_timeout(20000)
                            job_data = await self.extract_job_data(page)
                            print("job_data",job_data)
                    else:
                        print("No jobs found for ",speciality,location)
                    if count == len(locations) - 1:
                        await page.click("#multi-locations")
                        await page.wait_for_timeout(15000)
                        current_for_loc_value = f"d-{locations[count].lower()}"
                        await page.click(f'label[for="{current_for_loc_value}"]')
                        await page.wait_for_timeout(20000)
                except Exception as e:
                    print(f"An error occurred: {e}")
    

    async def extract_job_data(self, page):
        job_data = {}
        fields = [
            {
                "key": "job_title",
                "selector": "h2.card-title",
                "formator": lambda x: x.strip().replace("Locum Tenens ", "",)
            },
            {
                "key": "job_id",
                "selector": ".job-number",
                "formator": lambda x: x.split('JOB-')[1]
            },
            {
                "key": "job_description",
                "selector": ".job-detail .quick-facts",
                "content": True
            },
        ]
        for field in fields:
            element = await page.query_selector(field["selector"])
            if element:
                value = await element.inner_text()
                html = await element.inner_html()
                if "content" in field:
                    if "content" in job_data:
                        job_data['content'] += f"<li>{html}</li>"
                    else:
                        job_data['content'] = f"<li>{html}</li>"
                if "formator" in field:
                    val = field["formator"](value)
                    if isinstance(val, dict):
                        job_data.update(val)
                    else:
                        job_data[field["key"]] = val
                else:
                    job_data[field["key"]] = value
            else:
                job_data[field["key"]] = None
        return job_data


    async def extract_options(self, page, option_type):
        if option_type == 'profession':
            return ["Physician", "Nurse Practitioner","Physician Assistant"]
        elif option_type == 'speciality':
            labels = await page.query_selector_all('#multi-specialties .multi-select-wrap label')
            label_values = [await label.text_content() for label in labels]
            return label_values
        elif option_type == 'location':
            checkboxes = await page.query_selector_all('#multi-locations .multi-select-wrap input[type="checkbox"]')
            values = [await checkbox.get_attribute('value') for checkbox in checkboxes]
            values = [value.upper() for value in values if value.isalpha() and len(value) == 2]
            return values

    def extract_and_check_same(self, text):
        # Use regular expression to extract "x of y" pattern
        match = re.search(r'(\d+) of (\d+)', text)
        
        if match:
            # Extract the two numbers
            x = int(match.group(1))
            y = int(match.group(2))
            
            # Check if x and y are the same
            if x == y:
                return False
            else:
                return True
        else:
            return False  # Return False if "x of y" pattern is not found

    async def extract_no_of_jobs(self,page):
        data = await page.query_selector('.showing-jobs')
        value = await data.inner_text()
        return value

    async def scroll_to_bottom_and_load_all_content(self, page, wait_time=10):
        async def scroll_to_bottom():
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

        while True:
            jobs = await page.query_selector(".showing-jobs")
            show_jobs_pages = await jobs.inner_text()
            if self.extract_and_check_same(show_jobs_pages) == False:
                break

            # Scroll to the bottom to load more content
            await scroll_to_bottom()
            await asyncio.sleep(wait_time)