import argparse
import queue
import sys
import threading
from installer_core import install, detect_roots


def gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root = tk.Tk()
    root.title('BMS Korean Briefing · 설치')
    root.geometry('730x490')
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=28)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='BMS Korean Briefing', font=('Malgun Gothic', 21, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='BMS 실행 → PRINT → 한국어 브리핑', font=('Malgun Gothic', 11)).pack(anchor='w', pady=(4, 20))
    ttk.Label(frame, text='Falcon BMS 설치 폴더 (Bin, Data, User가 있는 폴더)').pack(anchor='w')
    choices = detect_roots()
    path = tk.StringVar(value=choices[0] if choices else '')
    row = ttk.Frame(frame)
    row.pack(fill='x', pady=8)
    entry = ttk.Combobox(row, textvariable=path, values=choices)
    entry.pack(side='left', fill='x', expand=True)

    def browse():
        selected = filedialog.askdirectory(title='Falcon BMS 설치 폴더 선택')
        if selected:
            path.set(selected)

    ttk.Button(row, text='폴더 선택', command=browse).pack(side='right', padx=(8, 0))
    ttk.Label(frame,text=f'설치 경로 {len(choices)}개 감지됨 · 여러 설치본은 목록에서 선택 / 직접 입력·폴더 선택 가능',font=('Malgun Gothic',9)).pack(anchor='w')
    integrate = tk.BooleanVar(value=True)
    ttk.Checkbutton(frame, text='기존 BMS 바로가기에 자동 실행 연결 (원래 바로가기는 백업)', variable=integrate).pack(anchor='w', pady=7)
    ttk.Label(frame, text='설치 위치: BMS\\User\\Plugins\\BMS-Korean-Briefing\nPython · Ollama · API 키 불필요 / 로그인 시 런처 실행 감지기 자동 시작\nFalcon BMS 공식 인증 제품이 아닌 독립적인 커뮤니티 애드온입니다.', font=('Malgun Gothic', 9), foreground='#52616b').pack(anchor='w', pady=8)
    status = tk.StringVar(value='설치 후 평소 BMS 바로가기로 실행하고 PRINT를 누르세요.')
    ttk.Label(frame, textvariable=status, wraplength=620).pack(anchor='w', pady=8)
    messages = queue.Queue()
    busy = False

    def begin():
        nonlocal busy
        selected = path.get()
        use_links = integrate.get()
        busy = True
        button.config(state='disabled')

        def task():
            try:
                dest = install(selected, integrate=use_links, progress=lambda s: messages.put(('status', s)))
                messages.put(('done', str(dest)))
            except Exception as exc:
                messages.put(('error', str(exc)))

        threading.Thread(target=task, daemon=True).start()

    button = ttk.Button(frame, text='설치 및 BMS 연결', command=begin)
    button.pack(anchor='e', pady=8)

    def update():
        nonlocal busy
        try:
            while True:
                kind, value = messages.get_nowait()
                status.set(value)
                if kind in ('done', 'error'):
                    busy = False
                    button.config(state='normal')
                if kind == 'done':
                    messagebox.showinfo('설치 완료', 'BMS 실행 감지기를 등록했습니다.\n런처 직접 실행과 이미 실행 중인 게임도 자동 연결합니다.\n\n' + value)
                elif kind == 'error':
                    messagebox.showerror('설치 확인', value)
        except queue.Empty:
            pass
        root.after(150, update)

    def close():
        if not busy:
            root.destroy()

    root.protocol('WM_DELETE_WINDOW', close)
    update()
    root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bms-root')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--no-integrate', action='store_true')
    parser.add_argument('--payload')
    parser.add_argument('--self-test-report')
    parser.add_argument('--update',action='store_true')
    parser.add_argument('--expected-version')
    args = parser.parse_args()
    if args.update:
        if not args.bms_root or not args.expected_version:parser.error('업데이트에는 기존 BMS 경로와 버전이 필요합니다.')
        from update_install import perform
        result=perform(args.bms_root,args.expected_version)
        if not result['ok']:raise SystemExit(1)
        return
    if args.self_test_report:
        import hashlib
        import json
        from pathlib import Path
        from installer_core import release_payload, EXE_NAME
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        payload = release_payload()
        expected = json.loads((payload / 'release.json').read_text('utf-8'))['sha256']
        valid = hashlib.sha256((payload / EXE_NAME).read_bytes()).hexdigest() == expected
        if not valid:
            raise RuntimeError('Embedded payload checksum mismatch')
        Path(args.self_test_report).write_text(json.dumps({'payload_checksum': valid, 'tkinter_runtime': True, 'korean_guide': (payload / '초기설치안내.html').exists()}, indent=2), 'utf-8')
        return
    if args.install:
        if not args.bms_root:
            parser.error('--bms-root is required')
        destination = install(args.bms_root, payload=args.payload, integrate=not args.no_integrate)
        if sys.stdout:
            print(destination)
        return
    gui()


if __name__ == '__main__':
    main()
