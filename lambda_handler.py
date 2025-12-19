import json
import boto3
from datetime import datetime
import requests
import xmltodict
import re

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
BUCKET_NAME = "medlaunch-regulations-data"

TITLE = 42
PART = 482
SUB_PARTS = ["A", "B", "C", "D", "E"]


titles_url = "https://www.ecfr.gov/api/versioner/v1/titles.json"
headers = {"Accept": "application/json"}

response = requests.get(titles_url, headers=headers)
response.raise_for_status()

data = response.json()
titles = data["titles"]
title_42 = next(title for title in titles if title["number"] == TITLE)


def create_a_sub_requirement(text, standard_code):
    sub = dict()
    text = text.strip()
    code_number = ""

    sub["code"] = ""  # Just to make it come first
    sub["text"] = text.strip()

    while sub["text"][0] == "(" and len(sub["text"].split(" ", 1)) > 1:
        code_number = sub["text"].split()[0].strip()
        sub["code"] = standard_code + (
            ""
            if standard_code
            and len(standard_code) > 1
            and code_number
            and len(code_number) > 1
            and code_number[1] == standard_code[-2]
            else code_number
        )
        sub["text"] = sub["text"].split(" ", 1)[1].strip()

    return sub


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def process_section_content(
    facility_type,
    part_label,
    title_number,
    version,
    effective_date,
    federal_register_citation,
    extraction_date,
    source_url,
    sub_part,
    sub_part_name,
    section_data,
    description,
):

    # Pattern hierarchies lowercase -> number -> roman -> uppercase
    is_a_upper_pattern = re.compile(r"^\([A-Z]")
    is_a_roman_pattern = re.compile(r"^\([ivxlcdm]")
    is_a_lower_case_pattern = re.compile(r"^\([a-hj-uwyz]")
    is_a_number_pattern = re.compile(r"^\([1-9]")

    section_data = json.dumps(section_data, ensure_ascii=False)
    section_data = json.loads(section_data)

    section_id = section_data["@N"]
    file_name = section_id.replace(".", "_")
    print("Saving", file_name)

    section_dict = dict()
    section_dict["regulation_id"] = (
        section_data["@hierarchy_metadata"]
        .split(":")[-1]
        .replace(" ", "_")
        .replace(".", "_")
        .replace('"', "")
        .replace("}", "")
    )
    section_dict["regulation_source"] = "cms_cop"
    section_dict["code"] = section_id
    section_dict["title"] = section_data["HEAD"].split(section_id, 1)[1].strip()
    section_dict["description"] = description
    section_dict["subpart"] = sub_part
    section_dict["subpart_name"] = sub_part_name
    contents_array = []

    # Some Ps are just strings
    source_array = (
        section_data["P"]
        if isinstance(section_data["P"], list)
        else [section_data["P"]]
    )

    current_content_dict = dict()
    last_number_sub_requirement = dict()
    last_roman_sub_requirement = dict()
    last_lower_sub_requirement = dict()
    last_upper_sub_requirement = dict()
    jump_from_lower_to_numeral = False

    for content in source_array:
        it_is_a_lower = isinstance(content, str) and bool(
            is_a_lower_case_pattern.match(content.strip())
        )
        if isinstance(content, dict) or it_is_a_lower:
            if len(current_content_dict.keys()) > 0:
                contents_array.append(current_content_dict)
            current_content_dict = dict()

            text = ""
            if it_is_a_lower:
                text = content.strip()
            else:
                text = content["#text"].strip()

            current_content_dict["standard_code"] = section_id + (
                text.split(" ")[0] if text[0] == "(" else ""
            )

            # Do requirement
            if it_is_a_lower:
                current_content_dict["requirement"] = ""
            else:
                current_content_dict["requirement"] = (
                    content["I"][0].strip().strip(".")
                    if isinstance(content["I"], list)
                    else content["I"].strip().strip(".")
                )

            # Create the first sub requirement unit
            last_lower_sub_requirement = create_a_sub_requirement(
                text, current_content_dict["standard_code"]
            )

            sub_requirements = current_content_dict.get("sub_requirements", [])
            sub_requirements.append(last_lower_sub_requirement)
            current_content_dict["sub_requirements"] = sub_requirements

            # To take care of items that have letter and number on one line
            if len(last_lower_sub_requirement["code"]) > 2 and is_number(
                last_lower_sub_requirement["code"][-2]
            ):
                jump_from_lower_to_numeral = True
                last_number_sub_requirement = last_lower_sub_requirement
            else:
                jump_from_lower_to_numeral = False

        else:
            # For number sub requirements
            if bool(is_a_number_pattern.match(content.strip())):
                # To take care of items that have letter and number on one line
                lower_or_main = dict()
                if jump_from_lower_to_numeral:
                    lower_or_main = current_content_dict
                else:
                    lower_or_main = last_lower_sub_requirement

                last_number_sub_requirement = create_a_sub_requirement(
                    content.strip(),
                    (
                        lower_or_main["code"]
                        if lower_or_main.get("code", False)
                        else lower_or_main["standard_code"]
                    ),
                )

                sub_requirements = lower_or_main.get("sub_requirements", [])
                sub_requirements.append(last_number_sub_requirement)
                lower_or_main["sub_requirements"] = sub_requirements

            # For roman numerals sub requirements
            elif bool(is_a_roman_pattern.match(content.strip())):
                last_roman_sub_requirement = create_a_sub_requirement(
                    content.strip(), last_number_sub_requirement["code"]
                )
                sub_requirements = last_number_sub_requirement.get(
                    "sub_requirements", []
                )
                sub_requirements.append(last_roman_sub_requirement)
                last_number_sub_requirement["sub_requirements"] = sub_requirements

            # For capital letter sub requirements
            elif bool(is_a_upper_pattern.match(content.strip())):
                last_upper_sub_requirement = create_a_sub_requirement(
                    content.strip(), last_roman_sub_requirement["code"]
                )
                sub_requirements = last_roman_sub_requirement.get(
                    "sub_requirements", []
                )
                sub_requirements.append(last_upper_sub_requirement)
                last_roman_sub_requirement["sub_requirements"] = sub_requirements
                pass

            # For first level section
            else:
                sub_requirements = current_content_dict.get("sub_requirements", [])
                last_level_2_sub_requirement = create_a_sub_requirement(
                    content.strip(),
                    current_content_dict.get("standard_code", section_id),
                )
                sub_requirements.append(last_level_2_sub_requirement)
                if not current_content_dict.get("requirement", None):
                    current_content_dict["requirement"] = ""
                current_content_dict["sub_requirements"] = sub_requirements

    if len(current_content_dict.keys()) > 0:
        contents_array.append(current_content_dict)

    section_dict["content"] = contents_array

    section_dict["metadata"] = {
        "facility_type": facility_type,
        "part_label": part_label,
        "title_number": title_number,
        "version": version,
        "effective_date": effective_date,
        "federal_register_citation": federal_register_citation,
        "extraction_date": extraction_date,
        "source_url": source_url,
    }

    return section_dict


def summarize_json(json_text):
    prompt = f"Summarize this JSON data in one sentence: {json_text}"

    body = json.dumps(
        {
            "inputText": prompt,
            "textGenerationConfig": {"maxTokenCount": 100, "temperature": 0.1},
        }
    )

    response = bedrock.invoke_model(
        body=body,
        modelId="amazon.titan-text-express-v1",
        accept="application/json",
        contentType="application/json",
    )

    result = json.loads(response["body"].read())
    return result["results"][0]["outputText"].strip()


def process_sections(sections, sub_part):
    for section in sections:
        bedrock_description = summarize_json(json.dumps(section))
        # Process
        processed_section = process_section_content(
            "Hospital",
            f"Part {PART}",
            TITLE,
            "2025-09-29",
            "2025-09-29",
            "Not specified",
            "2025-11-05T02:48:03.508545Z",
            "[https://www.ecfr.gov/current/title-42/section-482.1](https://www.ecfr.gov/current/title-42/section-482.1)",
            sub_part,
            "General Provisions",
            section,
            description=bedrock_description,
        )

        # Save processed
        # niaho-mapper-output/cms-cop/title-42/part-482/subpart-A/482-1.json
        file_name = section["@N"].replace(".", "-")
        s3_key = f"niaho-mapper-output/cms-cop/title-{TITLE}/part-{PART}/subpart-{sub_part}/{file_name}.json"

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(processed_section, ensure_ascii=False, indent=2),
            ContentType="application/json",
        )


def lambda_handler(event, context):
    try:
        for sub_part in SUB_PARTS:
            content_url = f"https://www.ecfr.gov/api/versioner/v1/full/{title_42['up_to_date_as_of']}/title-{TITLE}.xml?part={PART}&subpart={sub_part}"
            headers = {"Accept": "application/xml"}

            response = requests.get(content_url, headers=headers)
            response.raise_for_status()

            data = xmltodict.parse(response.text)

            if "DIV6" in data.keys():
                sub_part_data = data["DIV6"]
                if "DIV8" in sub_part_data.keys():
                    sections = sub_part_data["DIV8"]
                    process_sections(sections, sub_part)

                if "DIV7" in sub_part_data.keys():
                    sub_group = sub_part_data["DIV7"]
                    for idx in range(len(sub_group)):
                        if "DIV8" in sub_group[idx].keys():
                            sections = sub_group[idx]["DIV8"]
                            process_sections(
                                [sections] if isinstance(sections, dict) else sections,
                                sub_part,
                            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Data processed and saved successfully",
                    "s3_location": f"s3://{BUCKET_NAME}",
                }
            ),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
