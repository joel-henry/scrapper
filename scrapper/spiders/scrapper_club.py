import scrapy
from playwright.async_api import async_playwright
import time
import re
import asyncio

class ScrapperClubSpider(scrapy.Spider):
    name = "scrapper-club"
    allowed_domains = ["amnhealthcare.com"]

    def start_requests(self):
        url = "https://www.amnhealthcare.com/jobs/c/Physician/"
        yield scrapy.Request(url, meta={"playwright": True})

    async def parse(self, response):
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True, timeout=30000)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(response.url)
                await page.wait_for_load_state("domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"An error occurred: {e}")
            await page.wait_for_timeout(10000)
            locations = await self.extract_options(page, 'location')     
            for count, location in enumerate(locations):
                print("count",count)
                try:
                    for_loc_value = f"filters=Location:{location}"
                    url_with_params = f"{response.url}?{for_loc_value}"
                    await self.parse_results(url_with_params)
                except Exception as e:
                    print(f"An error occurred: {e}")

    async def parse_results(self, url):
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                print(url)
                await page.goto(url)
                await page.wait_for_load_state("domcontentloaded", timeout=60000)
                # Extract job details from the page and yield the results
                jobs = await page.query_selector(".count")
                if jobs:
                    jobs_count,job_urls = await self.get_job_data(page)
                    print("jobs_count",jobs_count)
                    if (len(job_urls) != jobs_count):
                        jobs_count,job_urls = await self.scroll_to_bottom_and_load_all_content(page)
                        # Print the job URLs
                        for job_url in job_urls:
                            await self.extract_job_details(job_url)
                            print("Job URL:", job_url)
            except Exception as e:
                self.logger.error(f"An error occurred while parsing results: {e}")

    async def extract_job_details(self,url):
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                self.logger.info(f"Extracting info from url: {url}")
                await page.goto(url)
                await page.wait_for_load_state("domcontentloaded", timeout=60000)
                job_title_sel = await page.query_selector('.job-details-title')
                job_title = await job_title_sel.inner_text() if job_title_sel else "No job title found"

                skillset_sel = await page.query_selector('.skillset')
                skillset = await skillset_sel.inner_text() if skillset_sel else "No skillset found"

                job_type_sel = await page.query_selector('.job-type-tag')
                job_type = await job_type_sel.inner_text() if job_type_sel else "No job type found"
                
                job_id_sel = await page.query_selector('.title-bar')
                job_id = await job_id_sel.inner_text() if job_id_sel else "No job id found"

                overall_job_details_element = await page.query_selector(".community-job-details-overview")
                location_sel = await overall_job_details_element.query_selector('a p.body-small.text-left.mb-0')
                state = "No state found"
                span_elements = await location_sel.query_selector_all('span')
                if len(span_elements) > 4:
                    state = await span_elements[4].inner_text()

                pay_details_element = await page.query_selector('.community-job-details-overview-pay-details')
                if pay_details_element:
                    pay_mode_element = await pay_details_element.query_selector('.subtitle-two.text-left.mb-0')
                    pay_mode = await pay_mode_element.inner_text() if pay_mode_element else "No pay mode found"

                    pay_range_elements = await pay_details_element.query_selector_all('.text-chateau')
                    if len(pay_range_elements) >= 4:
                        minimum_wage = await pay_range_elements[1].inner_text()
                        maximum_wage = await pay_range_elements[4].inner_text()
                    else:
                        minimum_wage = "No minimum wage found"
                        maximum_wage = "No maximum wage found"
                else:
                    pay_mode = "No pay details found"
                    minimum_wage = "No minimum wage found"
                    maximum_wage = "No maximum wage found"

                
                job_details_element = await page.query_selector('div.community-job-details-body > div:nth-child(1) > div:nth-child(1) > div')
                job_details_list = await job_details_element.query_selector_all('ul > li')
                job_details = await job_details_element.evaluate('element => element.innerText') if job_details_element else "No Job details found"
                job_details = job_details.strip()
                print("---------------------------------------------")
                print("Job Id: ",job_id)
                print("Job-Title: ",job_title)
                print("Skillset: ",skillset)
                print("Job-Type: ",job_type)
                print("pay-mode: ",pay_mode)
                print("state: ",state)
                print("minimum wage: ",minimum_wage)
                print("maximum wage: ",maximum_wage)
                print("Jobdetails:",job_details)
                print("---------------------------------------------")

            except Exception as e:
                self.logger.error(f"An error occurred while parsing results: {e}")

    async def extract_options(self, page, option_type):
        if option_type == 'profession':
            return ["Physician", "Nurse Practitioner", "Physician Assistant"]
        elif option_type == 'speciality':
            labels = await page.query_selector_all('#multi-specialties .multi-select-wrap label')
            label_values = [await label.text_content() for label in labels]
            return label_values
        elif option_type == 'location':
            labels = await page.query_selector_all('label[for^="Location-"]')
            values = []

            for label in labels:
                input_element = await label.query_selector('input[type="checkbox"]')
                checkbox_id = await input_element.get_attribute('id')
                # Extract the state name from the id attribute
                match = re.match(r'Location-([\w\s,]+)-input$', checkbox_id, re.IGNORECASE)
                if match:
                    state = match.group(1) 
                    values.append(state.strip())

            # Ensure unique values
            values = list(set(values))
            return values
    
    async def get_job_data(self, page):
        jobs_count = None
        job_urls = []

        jobs = await page.query_selector(".count")
        if jobs:
            jobs_count = await jobs.inner_text()

        job_titles = await page.query_selector_all(".result-card-content-title")
        for job_element in job_titles:
            job_url = await job_element.get_attribute("href")
            job_url = 'https://www.amnhealthcare.com' + job_url
            job_urls.append(job_url)

        return jobs_count, job_urls

    async def scroll_to_bottom_and_load_all_content(self, page, wait_time=10):
        async def scroll_to_bottom():
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

        while True:
            jobs_count,job_urls = await self.get_job_data(page)
            self.logger.info(f"Jobs Count: {jobs_count}")
            self.logger.info(f"Jobs Urls Length {len(job_urls)}")
            if (len(job_urls) == int(jobs_count)):
                self.logger.info(f"Jobs Url count and Jobs count is matched stopped scrolling")
                break
            else:
                self.logger.info(f"Jobs Urls count and Jobs count is not matched scrolling")

            # Scroll to the bottom to load more content
            await scroll_to_bottom()
            await asyncio.sleep(wait_time)

        return jobs_count, job_urls


    def get_state_full_name(abbr):
        states = {
            'AL': 'Alabama',
            'AK': 'Alaska',
            'AZ': 'Arizona',
            'AR': 'Arkansas',
            'CA': 'California',
            'CO': 'Colorado',
            'CT': 'Connecticut',
            'DE': 'Delaware',
            'FL': 'Florida',
            'GA': 'Georgia',
            'HI': 'Hawaii',
            'ID': 'Idaho',
            'IL': 'Illinois',
            'IN': 'Indiana',
            'IA': 'Iowa',
            'KS': 'Kansas',
            'KY': 'Kentucky',
            'LA': 'Louisiana',
            'ME': 'Maine',
            'MD': 'Maryland',
            'MA': 'Massachusetts',
            'MI': 'Michigan',
            'MN': 'Minnesota',
            'MS': 'Mississippi',
            'MO': 'Missouri',
            'MT': 'Montana',
            'NE': 'Nebraska',
            'NV': 'Nevada',
            'NH': 'New Hampshire',
            'NJ': 'New Jersey',
            'NM': 'New Mexico',
            'NY': 'New York',
            'NC': 'North Carolina',
            'ND': 'North Dakota',
            'OH': 'Ohio',
            'OK': 'Oklahoma',
            'OR': 'Oregon',
            'PA': 'Pennsylvania',
            'RI': 'Rhode Island',
            'SC': 'South Carolina',
            'SD': 'South Dakota',
            'TN': 'Tennessee',
            'TX': 'Texas',
            'UT': 'Utah',
            'VT': 'Vermont',
            'VA': 'Virginia',
            'WA': 'Washington',
            'WV': 'West Virginia',
            'WI': 'Wisconsin',
            'WY': 'Wyoming'
        }
        abbr_formatted = abbr.capitalize()
        return states.get(abbr.upper(), abbr_formatted)