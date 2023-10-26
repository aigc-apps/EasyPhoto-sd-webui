import argparse
import json
import os
import random

import gradio as gr
import pandas as pd



def read_json(file_path: str):
    return json.load(open(file_path))

def read_jsonl(file_path: str):
    data = []
    with open(file_path, 'r') as file:
        for line in file:
            data.append(json.loads(line))
    return data

def write_jsonl(data: any, file_path: str):
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            pass
    with open(file_path, 'a') as f:
        json.dump(data, f, ensure_ascii=False)
        f.write('\n')

def save_result(id, submit_cnt, *eval_results):
    if submit_cnt >= template['max_once']:
        gr.Warning('您的提交太频繁了，感谢您的积极参与。\nYour submissions are too frequent, thank you for your active participation.')
        return None, [], None, None, draw_results(), submit_cnt
        
    if not all(eval_results):
        raise gr.Error('请完整填写所有问题的答案。\nPlease complete the answers to all questions.')
    if id in ids:
        ids.remove(id)
    item = id2data[id]
    result = {
        "id": id,
        "questions": template['questions'],
        "answers": []
    }
    for r in eval_results:
        if r == '持平/Tie':
            result['answers'].append('tie')
        elif r == '左边/Left':
            result['answers'].append('method1' if item['left'] == 'img1' else 'method2')
        elif r == '右边/Right':
            result['answers'].append('method2' if item['left'] == 'img1' else 'method1')

    results.append(result)
    write_jsonl(result, args.result_path)

    return next_item() + (submit_cnt + 1,)

def next_item():
    if len(ids) <= 0:
        gr.Info('感谢您参与EasyPhoto的评测，本次评测已全部完成~🥰\nThank you for participating in the EasyPhoto review, this review is complete ~🥰')
        return None, [], None, None, draw_results()
    id = random.choice(list(ids))
    if random.random() < 0.5:
        id2data[id]['left'] = 'img1'
        left_img = id2data[id]['img1']
        right_img = id2data[id]['img2']
    else:
        id2data[id]['left'] = 'img2'
        left_img = id2data[id]['img2']
        right_img = id2data[id]['img1']
        
    item = id2data[id]
    
    return item['id'], [(x, '') for x in item['reference_imgs']], left_img, right_img, draw_results()

def draw_results():
    if len(results) == 0:
        return None

    questions = template['questions']
    num_questions = len(questions)

    method1_win = [0] * num_questions
    tie = [0] * num_questions
    method2_win = [0] * num_questions

    for item in results:
        assert len(item['answers']) == num_questions
        for i in range(num_questions):
            if item['answers'][i] == 'method1':
                method1_win[i] += 1
            elif item['answers'][i] == 'tie':
                tie[i] += 1
            elif item['answers'][i] == 'method2':
                method2_win[i] += 1
            else:
                raise NotImplementedError()
    results_for_drawing = {}

    method1_win += [sum(method1_win) / len(method1_win)]
    tie += [sum(tie) / len(tie)]
    method2_win += [sum(method2_win) / len(method2_win)]

    results_for_drawing['Questions'] = (questions + ['Average']) * 3
    results_for_drawing['Win Rate'] = [x / len(results) * 100 for x in method1_win] + [x / len(results) * 100 for x in tie] + [x / len(results) * 100 for x in method2_win]

    results_for_drawing['Winner'] = [data[0]['method1']] * (num_questions + 1) + ['Tie'] * (num_questions + 1) + [data[0]['method2']] * (num_questions + 1)
    results_for_drawing = pd.DataFrame(results_for_drawing)
    return gr.BarPlot(
        results_for_drawing,
        x="Questions",
        y="Win Rate",
        color="Winner",
        title="Human Evaluation Result",
        vertical=False,
        width=450,
        height=300
    )



if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--template-file', default='default_template.json')
    parser.add_argument('--data-path', default='data/makeup_transfer/data.json')
    parser.add_argument('--result-path', default='data/makeup_transfer/result.jsonl')
    parser.add_argument('--port', type=int, default=80)

    args = parser.parse_args()
    # global data
    if not os.path.exists(args.template_file):
        args.template_file = './double_blind/default_template.json'
    template = read_json(args.template_file)
    data = read_json(args.data_path)

    id2data = {}
    for item in data:
        id2data[item['id']] = item

    ids = set(id2data.keys())

    if os.path.exists(args.result_path):
        results = read_jsonl(args.result_path)
        labeled_ids = set([x['id'] for x in results])
        ids = ids - labeled_ids
    else:
        results = []


    with gr.Blocks(title="EasyPhoto双盲评测", css="style.css") as app:
        id = gr.State()

        with gr.Column(visible=True, elem_id="start"):
            gr.Markdown('### 欢迎您参与EasyPhoto的本次评测。')
            gr.Markdown('### Welcome to this review of EasyPhoto.')
            with gr.Row():
                start_btn = gr.Button('开始 / Start')
        
        with gr.Column(visible=False, elem_id="main"):
            submit_cnt = gr.State(value=1)
            
            with gr.Row():
                with gr.Column(scale=3):
                    reference_imgs = gr.Gallery(
                        [],
                        columns=3,
                        rows=1, 
                        label="人物参考图片",
                        show_label=True,
                        elem_id='reference-imgs',
                        visible=template['show_references']
                    )
                with gr.Column(scale=1):
                    pass
                
            
            gr.Markdown('### 根据下面的图片和上面的参考图片（如果有），回答下面的问题。')
            with gr.Row():
                with gr.Column(scale=3):
                    with gr.Row():
                        left_img = gr.Image(show_label=False)
                        right_img = gr.Image(show_label=False)
                with gr.Column(scale=1):
                    pass
            
            eval_results = []
            for question in template['questions']:
                eval_results.append(gr.Radio(["左边/Left", "持平/Tie", "右边/Right"], label=question, elem_classes="question"))

            submit = gr.Button('提交 / Submit')
            next_btn = gr.Button('换一个 / Change Another')

            with gr.Accordion('查看结果/View Results', open=False):
                with gr.Row():
                    with gr.Column(scale=1):
                        plot = gr.BarPlot()
                    with gr.Column(scale=1):
                        pass

            
        start_btn.click(next_item, inputs=None, outputs=[id, reference_imgs, left_img, right_img, plot]).then(fn=None, _js="\
            () => {\
                document.querySelector('#start').style.display = 'none';\
                document.querySelector('#main').style.display = 'flex';\
            }\
        ", inputs=None, outputs=[]
        )
        submit.click(save_result, inputs=[id, submit_cnt] + eval_results, outputs=[id, reference_imgs, left_img, right_img, plot, submit_cnt])
        next_btn.click(next_item, inputs=None, outputs=[id, reference_imgs, left_img, right_img, plot])

    # 最高并发15
    app.queue(concurrency_count=15).launch(
        server_name="0.0.0.0",
        server_port=args.port,
        show_api=False
    )
