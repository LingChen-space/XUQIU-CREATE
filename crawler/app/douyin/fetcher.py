import re
import requests
from datetime import datetime

from urllib.parse import urlparse, parse_qs, quote

from .a_bogus import ABogus
from .browser_core import DOUYIN_CONTEXT_LOCALE, DOUYIN_SCREEN, start_douyin_transient_context

class DouyinAntiSpamException(Exception):
    pass

DOUYIN_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

DOUYIN_VIDEO_URL = "https://www.douyin.com/video/{}"
DOUYIN_VIDEO_SEARCH_URL = "https://www.douyin.com/search/{}?type=video"

# sort_type
DOUYIN_SEARCH_FILTER_SORT_TYPES = {
    "default": {
        "name": "综合排序",
        "index1": "0",
        "index2": "0",
        "value": "0"
    },
    "latest": {
        "name": "最新发布",
        "index1": "0",
        "index2": "1",
        "value": "2"
    },
    "most_like": {
        "name": "最多点赞",
        "index1": "0",
        "index2": "2",
        "value": "1"
    }
}
def get_filter_sort_type(filter_sort: str) -> dict:
    return DOUYIN_SEARCH_FILTER_SORT_TYPES.get(filter_sort, DOUYIN_SEARCH_FILTER_SORT_TYPES["default"])

# publish_time
DOUYIN_SEARCH_FILTER_DATE = {
    "all": {
        "name": "不限",
        "index1": "1",
        "index2": "0",
        "value": "0"
    },
    "one_day": {
        "name": "一天内",
        "index1": "1",
        "index2": "1",
        "value": "1"
    },
    "one_week": {
        "name": "一周内",
        "index1": "1",
        "index2": "2",
        "value": "7"
    },
    "half_year": {
        "name": "半年内",
        "index1": "1",
        "index2": "3",
        "value": "180"
    }
}
def get_filter_date(filter_date: str) -> dict:
    return DOUYIN_SEARCH_FILTER_DATE.get(filter_date, DOUYIN_SEARCH_FILTER_DATE["all"])

# filter_duration
DOUYIN_SEARCH_FILTER_DURATION = {
    "all": {
        "name": "不限",
        "index1": "2",
        "index2": "0",
        "value": "0"
    },
    "under_one_minute": {
        "name": "1分钟以下",
        "index1": "2",
        "index2": "1",
        "value": "0-1"
    },
    "one_to_five_minutes": {
        "name": "1-5分钟",
        "index1": "2",
        "index2": "1-5"
    },
    "over_five_minutes": {
        "name": "5分钟以上",
        "index1": "2",
        "index2": "5-10000"
    }
}
def get_filter_duration(filter_duration: str) -> dict:
    return DOUYIN_SEARCH_FILTER_DURATION.get(filter_duration, DOUYIN_SEARCH_FILTER_DURATION["all"])

# content_type
DOUYIN_SEARCH_FILTER_CONTENT_TYPE = {
    "all": {
        "name": "不限",
        "index1": "3",
        "index2": "0",
        "value": "0"
    },
    "video": {
        "name": "视频",
        "index1": "3",
        "index2": "1",
        "value": "1"
    },
    "image": {
        "name": "图文",
        "index1": "3",
        "index2": "2",
        "value": "2"
    }
}
def get_filter_content_type(filter_content_type: str) -> dict:
    return DOUYIN_SEARCH_FILTER_CONTENT_TYPE.get(filter_content_type, DOUYIN_SEARCH_FILTER_CONTENT_TYPE["all"])

async def get_douyin_video_search_response(search_word: str,
                                           cookie_data: dict = None,
                                           sort_type: dict = DOUYIN_SEARCH_FILTER_SORT_TYPES["default"],
                                           filter_date: dict = DOUYIN_SEARCH_FILTER_DATE["all"],
                                           filter_duration: dict = DOUYIN_SEARCH_FILTER_DURATION["all"],
                                           filter_content_type: dict = DOUYIN_SEARCH_FILTER_CONTENT_TYPE["all"],
                                           limit: int = 10,
                                           headless: bool | None = None,
                                           browser_method: str | None = None):
    
    page_url = DOUYIN_VIDEO_SEARCH_URL.format(search_word)
    context = await start_douyin_transient_context(
        target_url=page_url,
        initial_cookies=cookie_data,
        headless=headless,
        browser_method=browser_method,
        context_kwargs={
            "viewport": {"width": 1440, "height": 1000},
            "screen": DOUYIN_SCREEN,
            "locale": DOUYIN_CONTEXT_LOCALE,
        },
    )
    try:
        page = await context.new_page()
        await page.goto(page_url)
        await page.wait_for_load_state("load")

        try:
            await page.wait_for_selector('ul[data-e2e="scroll-list"]')
            await page.wait_for_timeout(1500)
        except Exception as e:
            try:
                if await page.is_visible(".captcha_container", timeout=3000):
                    raise Exception("遇到验证码！")
            except:
                pass
            raise Exception("页面加载失败！")

        # await page.evaluate('''document.querySelector('span > svg.arrow').parentElement.click()''')
        # await page.wait_for_timeout(2000)
        # await page.wait_for_selector('span[data-index1="1"][data-index2="2"]')
        # await page.wait_for_timeout(2000)

        async with page.expect_response(url_or_predicate=re.compile(r"/aweme/v1/web/search/item"),
                                        timeout=10000) as response:
            await page.click('span.btn-title')

            resp_value = await response.value
            
            req_url = resp_value.url
            parsed_url = urlparse(req_url)
            parsed_qs = parse_qs(parsed_url.query)

            resp_json = await resp_value.json()
            # print(len(resp_json.get("data", [])))
            search_id = resp_json["extra"]["logid"]
            web_id = parsed_qs.get("webid", [None])[0]
            a_bogus = parsed_qs.get("a_bogus", [None])[0]

            # get current douyin.com cookie
            cookies = await page.context.cookies()

            cookie_str = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

            response_items = get_douyin_video_search_items(keyword=search_word,
                                                 sort_type=sort_type,
                                                 filter_date=filter_date,
                                                 filter_duration=filter_duration,
                                                 search_id=search_id,
                                                 cookie=cookie_str,
                                                 webid=web_id,
                                                 a_bogus=a_bogus,
                                                 limit=limit)
            
            if len(response_items) > 0:
                replace_cookie = cookies
            else:
                replace_cookie = None

            return response_items, replace_cookie
    finally:
        await context.close()
                                                    
DOUYIN_WEB_DATA_COLLECT_PARAMS = {
    "update_version_code": "170400",
    "pc_client_type": "1",
    "pc_libra_divert": "Windows",
    "support_h265": "1",
    "support_dash": "1",
    "cpu_core_num": "24",
    "version_code": "170400",
    "version_name": "17.4.0",
    "cookie_enabled": "true",
    "screen_width": "1920",
    "screen_height": "1080",
    "browser_language": "zh-CN",
    "browser_platform": "Win32",
    "browser_name": "Chrome",
    "browser_version": "128.0.0.0",
    "browser_online": "true",
    "engine_name": "Blink",
    "engine_version": "128.0.0.0",
    "os_name": "Windows",
    "os_version": "10",
    "device_memory": "8",
    "platform": "PC",
    "downlink": "10",
    "effective_type": "4g",
    "round_trip_time": "100",
}

API_DOUYIN_SEARCH_ITEM = "https://www.douyin.com/aweme/v1/web/search/item"

def api_get_douyin_search_item(keyword: str,
                               sort_type: str,
                               filter_date: str,
                               filter_duration: str,
                               search_id: str,
                               cookie: str = "",
                               referer: str = None,
                               webid: str = None,
                               a_bogus: str = None,
                               offset: int = 0):
    
    # device_platform=webapp&aid=6383&channel=channel_pc_web&search_channel=aweme_video_web&enable_history=1&sort_type=0&publish_time=1&keyword=%E6%97%A0%E7%95%8F%E5%A5%91%E7%BA%A6&search_source=tab_search&query_correct_type=1&is_filter_search=1&from_group_id=&offset=0&count=10&need_filter_settings=1&list_type=single&update_version_code=170400&pc_client_type=1&pc_libra_divert=Windows&support_h265=1&support_dash=1&cpu_core_num=24&version_code=170400&version_name=17.4.0&cookie_enabled=true&screen_width=1920&screen_height=1080&browser_language=zh-CN&browser_platform=Win32&browser_name=Chrome&browser_version=138.0.0.0&browser_online=true&engine_name=Blink&engine_version=138.0.0.0&os_name=Windows&os_version=10&device_memory=8&platform=PC&downlink=10&effective_type=4g&round_trip_time=100&webid=7530454861046351379&uifid=1b474bc7e0db9591e645dd8feb8c65aae4845018effd0c2743039a380ee647404517b1b1ba3e10cc815974451acc5458115eb53d7d35edac86829c9c3470c8e41f73f5121657706c8bd62ddb27c2ab41&msToken=FhDyAQfxkhB4VT8NWEXnxR_NMcYbvKIBOVRHzBvBROLeR1rvKcSOPUexFmphjAAZH0k5O1ax30gjMRlujFTtNWInkWqSPdol3ZCouE7QpL8njU21xL6wgpzVoF2Jm3wfTCeNwrtdQwZ3f_w4sXum68SpI297JRxcKTHLXCTzTPms1T7C2LqGvg%3D%3D&a_bogus=Qvsfhzt7EZ%2FROd%2FGuKQY7v-lZwdANTSyJsioRTFlSNw9cZMbmuNAwcSorouT3DcGymBTiKQ7GDUAGdVbz0tkZHekLspvSOGWV0dIVt6LZZ7DbBJ2V1jZeitxKv4a0STOKQIbEai1X0z72oc3irn%2FA33aC5zPQQbDbNFSd2mcJ9ANVWDHnnQfeBgK
    params = {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "search_channel": "aweme_video_web",
        "enable_history": "1",
        "is_filter_search": "1",
        "keyword": keyword,
        "search_source": "tab_search",
        "query_correct_type": "1",
        "from_group_id": "",
        "offset": offset,
        "count": "10",
        "need_filter_settings": "1",
        "list_type": "single",
        "search_id": search_id,
    }
    if webid is not None:
        params["webid"] = webid

    params.update(DOUYIN_WEB_DATA_COLLECT_PARAMS)

    params["sort_type"] = sort_type
    params["publish_time"] = filter_date
    params["filter_duration"] = filter_duration

    if sort_type == "0" and filter_date == "0" and filter_duration == "0":
        del params["sort_type"]
        del params["publish_time"]
        del params["filter_duration"]
        params["search_source"] = "normal_search"
        params["is_filter_search"] = 0

    if offset > 0:
        params['need_filter_settings'] = 0

    # params["verifyFp"] = VerifyFp.get_verify_fp()
    
    if a_bogus is not None:
        params["a_bogus"] = a_bogus
    else:
        a_bogus = ABogus(user_agent=DOUYIN_USER_AGENT)
        a_bogus_value = a_bogus.get_value(params, method="GET")
        params["a_bogus"] = a_bogus_value

    try:
        resp = requests.get(API_DOUYIN_SEARCH_ITEM,
                            params=params,
                            headers={
                                "Cookie": cookie,
                                "User-Agent": DOUYIN_USER_AGENT,
                                "Referer": referer if referer else "https://www.douyin.com/search/{}?type=video".format(quote(keyword)),
                                "uifid": "undefined"
                            })
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching Douyin search item: {e}")
        return None

    resp_data = resp.json()

    return resp_data

def get_douyin_video_search_items(keyword: str,
                                sort_type: dict,
                                filter_date: dict,
                                filter_duration: dict,
                                search_id: str = "",
                                cookie: str = "",
                                referer: str = "",
                                webid: str = None,
                                a_bogus: str = None,
                                limit: int = -1):
    
    sort_type = sort_type.get("value")
    publish_time = filter_date.get("value")
    filter_duration = filter_duration.get("value")

    collected_items = []

    curr_offset = 0
    has_next = True
    curr_retry_count = 0
    while has_next:
        if curr_retry_count >= 3:
            raise Exception("获取抖音搜索结果失败，超过最大重试次数")
        try:
            curr_search_resp = api_get_douyin_search_item(keyword=keyword,
                                                        sort_type=sort_type,
                                                        filter_date=publish_time,
                                                        filter_duration=filter_duration,
                                                        search_id=search_id,
                                                        cookie=cookie,
                                                        referer=referer,
                                                        webid=webid,
                                                        a_bogus=a_bogus,
                                                        offset=curr_offset)

            data = curr_search_resp.get("data", {})
            if len(data) == 0:
                if "search_nil_info" in curr_search_resp:
                    search_nil_info = curr_search_resp.get("search_nil_info", {})
                    if search_nil_info.get("search_nil_type") == "antispam_check":
                        raise DouyinAntiSpamException("触发风控！")
                    elif search_nil_info.get("search_nil_type") == "verify_check":
                        raise DouyinAntiSpamException("需要验证！")
            for item in data:
                aweme_info = item.get("aweme_info", {})

                video_id = aweme_info.get("aweme_id", "")
                video_desc = aweme_info.get("desc", "")
                video_url = "https://www.douyin.com/video/" + video_id

                create_time = aweme_info.get("create_time", 0)
                create_time_str = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")

                author_uid = aweme_info.get("author", {}).get("uid", "")
                author_sec_uid = aweme_info.get("author", {}).get("sec_uid", "")
                author_url = "https://www.douyin.com/user/" + author_sec_uid
                author_name = aweme_info.get("author", {}).get("nickname", "")

                like_count = aweme_info.get("statistics", {}).get("digg_count", 0)

                cover_image_urls = aweme_info.get("video", {}).get("cover", {}).get("url_list", [])
                origin_cover_image_urls = aweme_info.get("video", {}).get("origin_cover", {}).get("url_list", [])

                collected_items.append({
                    "video_id": video_id,
                    "video_desc": video_desc,
                    "video_url": video_url,
                    "author_uid": author_uid,
                    "author_sec_uid": author_sec_uid,
                    "author_url": author_url,
                    "author_name": author_name,
                    "like_count": like_count,
                    "timestamp": create_time,
                    "create_time": create_time_str,
                    "cover_image_urls": cover_image_urls,
                    "origin_cover_image_urls": origin_cover_image_urls
                })
            if limit > 0 and len(collected_items) >= limit:
                has_next = False
                break
   
            has_next = curr_search_resp.get("has_more", 0) == 1
            curr_offset += 10

            curr_retry_count = 0
        except DouyinAntiSpamException as ase:
            raise ase
        except Exception as e:
            curr_retry_count += 1

    return collected_items
