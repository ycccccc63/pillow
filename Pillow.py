import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
import numpy as np
from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageFilter, ImageDraw

class ImageConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("彩色影像模式轉換與 GIF 製作工具")
        self.root.geometry("1200x760")
        self.root.minsize(1000, 660)

        # 狀態變數
        self.src_image_path = None
        self.original_img = None     # PIL 原圖 (RGB)
        self.processed_img = None    # 處理後的預設影像

        # 拉普拉斯專用 (a/b/c 三張圖)
        self.laplacian_a = None
        self.laplacian_b = None
        self.laplacian_c = None

        # GIF 動畫專用變數
        self.gif_frames = []
        self.gif_preview_idx = 0
        self.gif_anim_id = None

        # 繪圖筆刷專用狀態
        self.last_x = None
        self.last_y = None
        self.preview_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # 紀錄上次視窗大小（防止無限放大迴圈）
        self.last_win_w = 0
        self.last_win_h = 0

        self._build_ui()

    def _build_ui(self):
        # 頂部操作欄
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(side=tk.TOP, fill=tk.X)

        self.btn_open = ttk.Button(top_frame, text="📁 開啟單張影像", command=self.load_image)
        self.btn_open.pack(side=tk.LEFT, padx=5)

        self.lbl_filepath = ttk.Label(top_frame, text="未選擇任何檔案", foreground="gray")
        self.lbl_filepath.pack(side=tk.LEFT, padx=10)

        self.btn_save = ttk.Button(top_frame, text="💾 儲存新檔 / 匯出 GIF", command=self.save_image, state=tk.DISABLED)
        self.btn_save.pack(side=tk.RIGHT, padx=5)

        # 主區域
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 左側控制選單
        control_frame = ttk.LabelFrame(main_frame, text="功能模式設定", padding="10")
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.mode_var = tk.StringVar(value="gray")
        
        ttk.Radiobutton(control_frame, text="1. 灰階 (Grayscale)", value="gray", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(control_frame, text="2. 純黑白 (二值化)", value="bw", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)

        self.frame_bw_param = ttk.Frame(control_frame)
        ttk.Label(self.frame_bw_param, text="臨界值 (Threshold):").pack(anchor=tk.W)
        self.scale_threshold = ttk.Scale(self.frame_bw_param, from_=0, to=255, value=128, command=self.on_param_change)
        self.scale_threshold.pack(fill=tk.X, pady=2)
        self.lbl_threshold_val = ttk.Label(self.frame_bw_param, text="128")
        self.lbl_threshold_val.pack(anchor=tk.E)

        ttk.Radiobutton(control_frame, text="3. 調色盤 (Palette)", value="palette", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)

        self.frame_palette_param = ttk.Frame(control_frame)
        ttk.Label(self.frame_palette_param, text="色彩數量 (2-256):").pack(anchor=tk.W)
        self.scale_colors = ttk.Scale(self.frame_palette_param, from_=2, to=256, value=16, command=self.on_param_change)
        self.scale_colors.pack(fill=tk.X, pady=2)
        self.lbl_colors_val = ttk.Label(self.frame_palette_param, text="16 色")
        self.lbl_colors_val.pack(anchor=tk.E)

        ttk.Radiobutton(control_frame, text="4. X-Ray 負片效果", value="xray", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(control_frame, text="5. 全圖中位數濾波", value="median", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)

        self.frame_median_param = ttk.Frame(control_frame)
        ttk.Label(self.frame_median_param, text="濾波核心大小 (Kernel):").pack(anchor=tk.W)
        self.scale_kernel = ttk.Scale(self.frame_median_param, from_=3, to=15, value=3, command=self.on_param_change)
        self.scale_kernel.pack(fill=tk.X, pady=2)
        self.lbl_kernel_val = ttk.Label(self.frame_median_param, text="3 x 3")
        self.lbl_kernel_val.pack(anchor=tk.E)

        ttk.Radiobutton(control_frame, text="6. 局部中位數濾波 (去噪刷)", value="local_median", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)

        self.frame_local_param = ttk.Frame(control_frame)
        ttk.Label(self.frame_local_param, text="去噪刷大小:").pack(anchor=tk.W)
        self.scale_brush = ttk.Scale(self.frame_local_param, from_=10, to=100, value=30, command=self.on_param_change)
        self.scale_brush.pack(fill=tk.X, pady=2)
        self.lbl_brush_val = ttk.Label(self.frame_local_param, text="30 px")
        self.lbl_brush_val.pack(anchor=tk.E)

        ttk.Radiobutton(control_frame, text="7. 拉普拉斯濾波器 (銳化)", value="laplacian", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(control_frame, text="8. 繪圖筆刷 (鋼筆/螢光/蠟筆)", value="art_brush", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)

        # 8. 繪圖筆刷參數面板
        self.frame_art_brush_param = ttk.LabelFrame(control_frame, text="筆刷與 RGB 調色設定", padding="6")
        self.art_brush_type = tk.StringVar(value="pen")
        ttk.Radiobutton(self.frame_art_brush_param, text="🖋️ 鋼筆 (銳利實線)", value="pen", variable=self.art_brush_type).pack(anchor=tk.W, pady=1)
        ttk.Radiobutton(self.frame_art_brush_param, text="🖍️ 螢光筆 (半透明疊加)", value="highlighter", variable=self.art_brush_type).pack(anchor=tk.W, pady=1)
        ttk.Radiobutton(self.frame_art_brush_param, text="🖍️ 蠟筆 (粗糙顆粒質感)", value="crayon", variable=self.art_brush_type).pack(anchor=tk.W, pady=1)

        ttk.Separator(self.frame_art_brush_param, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        preview_color_row = ttk.Frame(self.frame_art_brush_param)
        preview_color_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(preview_color_row, text="目前顏色:").pack(side=tk.LEFT)
        self.color_preview_box = tk.Label(preview_color_row, text="      ", bg="#eb2d2d", relief=tk.SOLID, borderwidth=1)
        self.color_preview_box.pack(side=tk.LEFT, padx=5)
        ttk.Button(preview_color_row, text="🎨 調色盤", width=8, command=self.open_color_picker).pack(side=tk.RIGHT)

        row_r = ttk.Frame(self.frame_art_brush_param)
        row_r.pack(fill=tk.X, pady=1)
        ttk.Label(row_r, text="R:", width=2, foreground="#d93025").pack(side=tk.LEFT)
        self.scale_r = ttk.Scale(row_r, from_=0, to=255, value=235, command=self.update_rgb_display)
        self.scale_r.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.lbl_r_val = ttk.Label(row_r, text="235", width=3)
        self.lbl_r_val.pack(side=tk.RIGHT)

        row_g = ttk.Frame(self.frame_art_brush_param)
        row_g.pack(fill=tk.X, pady=1)
        ttk.Label(row_g, text="G:", width=2, foreground="#188038").pack(side=tk.LEFT)
        self.scale_g = ttk.Scale(row_g, from_=0, to=255, value=45, command=self.update_rgb_display)
        self.scale_g.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.lbl_g_val = ttk.Label(row_g, text="45", width=3)
        self.lbl_g_val.pack(side=tk.RIGHT)

        row_b = ttk.Frame(self.frame_art_brush_param)
        row_b.pack(fill=tk.X, pady=1)
        ttk.Label(row_b, text="B:", width=2, foreground="#1a73e8").pack(side=tk.LEFT)
        self.scale_b = ttk.Scale(row_b, from_=0, to=255, value=45, command=self.update_rgb_display)
        self.scale_b.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.lbl_b_val = ttk.Label(row_b, text="45", width=3)
        self.lbl_b_val.pack(side=tk.RIGHT)

        ttk.Separator(self.frame_art_brush_param, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Label(self.frame_art_brush_param, text="筆刷粗細:").pack(anchor=tk.W)
        self.scale_art_size = ttk.Scale(self.frame_art_brush_param, from_=2, to=50, value=12, command=self.on_param_change)
        self.scale_art_size.pack(fill=tk.X, pady=2)
        self.lbl_art_size_val = ttk.Label(self.frame_art_brush_param, text="12 px")
        self.lbl_art_size_val.pack(anchor=tk.E)
        ttk.Button(self.frame_art_brush_param, text="🔄 清除重畫", command=self.reset_brush_canvas).pack(fill=tk.X, pady=(5, 0))

        # 9. 製作 GIF 動畫功能
        ttk.Radiobutton(control_frame, text="9. 製作 GIF 動畫 (GIF Maker)", value="gif_maker", variable=self.mode_var, command=self.on_mode_change).pack(anchor=tk.W, pady=2)

        self.frame_gif_param = ttk.LabelFrame(control_frame, text="GIF 動畫設定", padding="6")
        ttk.Button(self.frame_gif_param, text="🖼️ 選取多張圖片合成 GIF", command=self.load_multiple_images_for_gif).pack(fill=tk.X, pady=2)
        ttk.Button(self.frame_gif_param, text="✨ 用目前圖片產生濾鏡動畫", command=self.generate_filter_gif).pack(fill=tk.X, pady=2)
        
        self.lbl_gif_info = ttk.Label(self.frame_gif_param, text="目前影格數：0 幀", foreground="#1a73e8")
        self.lbl_gif_info.pack(anchor=tk.W, pady=(4, 2))

        ttk.Label(self.frame_gif_param, text="每幀間隔時間 (速度):").pack(anchor=tk.W)
        self.scale_gif_duration = ttk.Scale(self.frame_gif_param, from_=50, to=1000, value=300, command=self.on_param_change)
        self.scale_gif_duration.pack(fill=tk.X, pady=2)
        self.lbl_gif_duration_val = ttk.Label(self.frame_gif_param, text="300 ms")
        self.lbl_gif_duration_val.pack(anchor=tk.E)

        # 右側預覽容器
        self.preview_frame = ttk.Frame(main_frame)
        self.preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 【關鍵修正 1】加上 pack_propagate(False)，鎖死容器大小不讓圖片把視窗越撐越大
        self.frame_orig = ttk.LabelFrame(self.preview_frame, text="原始彩色影像", padding="5")
        self.frame_orig.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.frame_orig.pack_propagate(False)
        self.lbl_orig_preview = ttk.Label(self.frame_orig, text="尚未載入圖片", anchor=tk.CENTER)
        self.lbl_orig_preview.pack(fill=tk.BOTH, expand=True)

        self.frame_proc = ttk.LabelFrame(self.preview_frame, text="轉換後預覽 (筆刷模式可在此作畫)", padding="5")
        self.frame_proc.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=2)
        self.frame_proc.pack_propagate(False)
        self.lbl_proc_preview = ttk.Label(self.frame_proc, text="尚未載入圖片", anchor=tk.CENTER)
        self.lbl_proc_preview.pack(fill=tk.BOTH, expand=True)

        # 拉普拉斯專用三對比框
        self.frame_lap_a = ttk.LabelFrame(self.preview_frame, text="(a) 原始灰階影像", padding="5")
        self.frame_lap_a.pack_propagate(False)
        self.lbl_lap_a = ttk.Label(self.frame_lap_a, text="無資料", anchor=tk.CENTER)
        self.lbl_lap_a.pack(fill=tk.BOTH, expand=True)

        self.frame_lap_b = ttk.LabelFrame(self.preview_frame, text="(b) Laplacian 遮罩處理結果", padding="5")
        self.frame_lap_b.pack_propagate(False)
        self.lbl_lap_b = ttk.Label(self.frame_lap_b, text="無資料", anchor=tk.CENTER)
        self.lbl_lap_b.pack(fill=tk.BOTH, expand=True)

        self.frame_lap_c = ttk.LabelFrame(self.preview_frame, text="(c) 結合(a)與(b)之銳化結果", padding="5")
        self.frame_lap_c.pack_propagate(False)
        self.lbl_lap_c = ttk.Label(self.frame_lap_c, text="無資料", anchor=tk.CENTER)
        self.lbl_lap_c.pack(fill=tk.BOTH, expand=True)

        # 滑鼠事件綁定
        self.lbl_proc_preview.bind("<Button-1>", self.on_mouse_down)
        self.lbl_proc_preview.bind("<B1-Motion>", self.on_mouse_drag)
        self.lbl_proc_preview.bind("<ButtonRelease-1>", self.on_mouse_up)

        self.root.bind("<Configure>", self.on_resize)

    def load_image(self):
        file_path = filedialog.askopenfilename(
            title="選擇彩色影像",
            filetypes=[("圖片檔案", "*.jpg *.jpeg *.png *.bmp *.webp"), ("所有檔案", "*.*")]
        )
        if not file_path:
            return

        try:
            self.src_image_path = file_path
            self.lbl_filepath.config(text=os.path.basename(file_path))
            self.original_img = Image.open(file_path).convert("RGB")
            
            self.btn_save.config(state=tk.NORMAL)
            self.on_mode_change()
            self.update_preview()
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟圖片：\n{e}")

    def stop_gif_animation(self):
        if self.gif_anim_id is not None:
            self.root.after_cancel(self.gif_anim_id)
            self.gif_anim_id = None

    def load_multiple_images_for_gif(self):
        file_paths = filedialog.askopenfilenames(
            title="按住 Ctrl 或 Shift 選取多張圖片 (依序組成 GIF)",
            filetypes=[("圖片檔案", "*.jpg *.jpeg *.png *.bmp *.webp"), ("所有檔案", "*.*")]
        )
        if not file_paths or len(file_paths) < 2:
            if file_paths:
                messagebox.showwarning("提示", "請至少選擇 2 張以上的圖片才能製作 GIF 動畫！")
            return

        try:
            self.stop_gif_animation()
            self.gif_frames = []
            
            first_img = Image.open(file_paths[0]).convert("RGB")
            base_size = first_img.size
            self.original_img = first_img
            self.src_image_path = file_paths[0]
            self.lbl_filepath.config(text=f"已選取 {len(file_paths)} 張圖片製作 GIF")

            for p in file_paths:
                img = Image.open(p).convert("RGB")
                if img.size != base_size:
                    img = img.resize(base_size, Image.Resampling.LANCZOS)
                self.gif_frames.append(img)

            self.lbl_gif_info.config(text=f"目前影格數：{len(self.gif_frames)} 幀")
            self.btn_save.config(state=tk.NORMAL)
            self.gif_preview_idx = 0
            self.play_gif_preview()
        except Exception as e:
            messagebox.showerror("錯誤", f"讀取多張圖片失敗：\n{e}")

    def generate_filter_gif(self):
        if self.original_img is None:
            messagebox.showwarning("提示", "請先點擊左上角「📁 開啟單張影像」載入一張圖片！")
            return

        self.stop_gif_animation()
        base = self.original_img.copy()
        gray = base.convert("L").convert("RGB")
        xray = ImageEnhance.Contrast(ImageOps.invert(base.convert("L"))).enhance(1.5).convert("RGB")
        quant = base.quantize(colors=8).convert("RGB")

        self.gif_frames = [base, gray, xray, quant]
        self.lbl_gif_info.config(text=f"目前影格數：{len(self.gif_frames)} 幀 (濾鏡循環)")
        self.btn_save.config(state=tk.NORMAL)
        self.gif_preview_idx = 0
        self.play_gif_preview()

    def play_gif_preview(self):
        if self.mode_var.get() != "gif_maker" or not self.gif_frames:
            return

        try:
            box_width = max(self.frame_orig.winfo_width() - 16, 150)
            box_height = max(self.frame_orig.winfo_height() - 30, 150)

            orig_resized, _, _, _ = self._resize_aspect_ratio(self.gif_frames[0], box_width, box_height)
            self.tk_orig_image = ImageTk.PhotoImage(orig_resized, master=self.root)
            self.lbl_orig_preview.config(image=self.tk_orig_image, text="")

            curr_frame = self.gif_frames[self.gif_preview_idx]
            proc_resized, _, _, _ = self._resize_aspect_ratio(curr_frame, box_width, box_height)
            self.tk_proc_image = ImageTk.PhotoImage(proc_resized, master=self.root)
            self.lbl_proc_preview.config(image=self.tk_proc_image, text="")

            self.gif_preview_idx = (self.gif_preview_idx + 1) % len(self.gif_frames)
            duration = int(self.scale_gif_duration.get())
            self.gif_anim_id = self.root.after(duration, self.play_gif_preview)
        except Exception as e:
            print(f"GIF 預覽錯誤: {e}")

    def reset_brush_canvas(self):
        if self.original_img:
            self.processed_img = self.original_img.copy()
            self.update_preview()

    def update_rgb_display(self, event=None):
        r = int(self.scale_r.get())
        g = int(self.scale_g.get())
        b = int(self.scale_b.get())

        self.lbl_r_val.config(text=str(r))
        self.lbl_g_val.config(text=str(g))
        self.lbl_b_val.config(text=str(b))

        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.color_preview_box.config(bg=hex_color)

    def open_color_picker(self):
        curr_rgb = self._get_rgb_color()
        color_code = colorchooser.askcolor(color=curr_rgb, title="選擇筆刷顏色")
        if color_code[0]:
            r, g, b = [int(c) for c in color_code[0]]
            self.scale_r.set(r)
            self.scale_g.set(g)
            self.scale_b.set(b)
            self.update_rgb_display()

    def _get_rgb_color(self):
        return (
            int(self.scale_r.get()),
            int(self.scale_g.get()),
            int(self.scale_b.get())
        )

    def process_image(self):
        if self.original_img is None:
            return

        mode = self.mode_var.get()

        if mode == 'gray':
            self.processed_img = self.original_img.convert('L')
        elif mode == 'bw':
            thresh = int(self.scale_threshold.get())
            gray = self.original_img.convert('L')
            self.processed_img = gray.point(lambda p: 255 if p > thresh else 0).convert('1')
        elif mode == 'palette':
            num_colors = int(self.scale_colors.get())
            self.processed_img = self.original_img.quantize(colors=num_colors)
        elif mode == 'xray':
            gray = self.original_img.convert('L')
            inverted = ImageOps.invert(gray)
            enhancer = ImageEnhance.Contrast(inverted)
            self.processed_img = enhancer.enhance(1.5)
        elif mode == 'median':
            k_size = int(self.scale_kernel.get())
            if k_size % 2 == 0:
                k_size += 1
            self.processed_img = self.original_img.filter(ImageFilter.MedianFilter(size=k_size))
        elif mode in ('local_median', 'art_brush'):
            if self.processed_img is None or self.processed_img.size != self.original_img.size or self.processed_img.mode != self.original_img.mode:
                self.processed_img = self.original_img.copy()
        elif mode == 'laplacian':
            gray_img = self.original_img.convert('L')
            self.laplacian_a = gray_img
            gray_np = np.array(gray_img, dtype=np.float32)

            lap_filter = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1.0, offset=0)
            edge_img = gray_img.filter(lap_filter)
            edge_np = np.array(edge_img, dtype=np.float32)

            edge_vis = np.clip(np.abs(edge_np) * 1.5, 0, 255).astype(np.uint8)
            self.laplacian_b = Image.fromarray(edge_vis)

            sharpened_np = np.clip(gray_np - edge_np, 0, 255).astype(np.uint8)
            self.laplacian_c = Image.fromarray(sharpened_np)

            self.processed_img = self.laplacian_c
        elif mode == 'gif_maker':
            if not self.gif_frames and self.original_img:
                self.generate_filter_gif()

    def _get_image_coords(self, event):
        img_x = int((event.x - self.offset_x) / self.preview_scale)
        img_y = int((event.y - self.offset_y) / self.preview_scale)
        return img_x, img_y

    def on_mouse_down(self, event):
        if self.original_img is None:
            return
        self.last_x, self.last_y = self._get_image_coords(event)
        self.on_mouse_drag(event)

    def on_mouse_up(self, event):
        self.last_x = None
        self.last_y = None

    def on_mouse_drag(self, event):
        mode = self.mode_var.get()
        if self.original_img is None or mode not in ('local_median', 'art_brush'):
            return

        curr_x, curr_y = self._get_image_coords(event)
        w, h = self.original_img.size

        if not (0 <= curr_x < w and 0 <= curr_y < h):
            return

        if mode == 'local_median':
            brush_size = int(self.scale_brush.get())
            radius = brush_size // 2
            left, top = max(0, curr_x - radius), max(0, curr_y - radius)
            right, bottom = min(w, curr_x + radius), min(h, curr_y + radius)
            if right > left and bottom > top:
                crop_box = (left, top, right, bottom)
                filtered = self.processed_img.crop(crop_box).filter(ImageFilter.MedianFilter(size=5))
                self.processed_img.paste(filtered, crop_box)

        elif mode == 'art_brush':
            b_type = self.art_brush_type.get()
            size = int(self.scale_art_size.get())
            rgb = self._get_rgb_color()
            
            x1 = self.last_x if self.last_x is not None else curr_x
            y1 = self.last_y if self.last_y is not None else curr_y

            if b_type == 'pen':
                draw = ImageDraw.Draw(self.processed_img)
                draw.line([(x1, y1), (curr_x, curr_y)], fill=rgb, width=size)
                r = size // 2
                draw.ellipse([curr_x - r, curr_y - r, curr_x + r, curr_y + r], fill=rgb)

            elif b_type == 'highlighter':
                overlay = Image.new("RGBA", self.processed_img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                rgba_color = (*rgb, 90)
                
                draw.line([(x1, y1), (curr_x, curr_y)], fill=rgba_color, width=int(size * 1.5))
                r = int(size * 0.75)
                draw.ellipse([curr_x - r, curr_y - r, curr_x + r, curr_y + r], fill=rgba_color)

                base_rgba = self.processed_img.convert("RGBA")
                combined = Image.alpha_composite(base_rgba, overlay)
                self.processed_img = combined.convert("RGB")

            elif b_type == 'crayon':
                draw = ImageDraw.Draw(self.processed_img)
                dist = max(1, int(np.hypot(curr_x - x1, curr_y - y1)))
                steps = max(1, dist // 2)
                radius = max(2, size // 2)

                for s in range(steps + 1):
                    t = s / steps
                    cx = int(x1 + (curr_x - x1) * t)
                    cy = int(y1 + (curr_y - y1) * t)

                    num_dots = size * 3
                    for _ in range(num_dots):
                        angle = random.uniform(0, 2 * np.pi)
                        r_offset = random.uniform(0, radius) ** 0.7 * (radius ** 0.3)
                        px = int(cx + r_offset * np.cos(angle))
                        py = int(cy + r_offset * np.sin(angle))

                        if 0 <= px < w and 0 <= py < h:
                            jitter = random.randint(-20, 20)
                            c_r = max(0, min(255, rgb[0] + jitter))
                            c_g = max(0, min(255, rgb[1] + jitter))
                            c_b = max(0, min(255, rgb[2] + jitter))
                            draw.point((px, py), fill=(c_r, c_g, c_b))

        self.last_x, self.last_y = curr_x, curr_y
        self.update_preview()

    def on_mode_change(self):
        mode = self.mode_var.get()
        self.stop_gif_animation()
        
        self.frame_bw_param.pack_forget()
        self.frame_palette_param.pack_forget()
        self.frame_median_param.pack_forget()
        self.frame_local_param.pack_forget()
        self.frame_art_brush_param.pack_forget()
        self.frame_gif_param.pack_forget()

        if mode == 'laplacian':
            self.frame_orig.pack_forget()
            self.frame_proc.pack_forget()
            
            self.frame_lap_a.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            self.frame_lap_b.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            self.frame_lap_c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        else:
            self.frame_lap_a.pack_forget()
            self.frame_lap_b.pack_forget()
            self.frame_lap_c.pack_forget()

            self.frame_orig.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            self.frame_proc.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=2)

            if mode == 'bw':
                self.frame_bw_param.pack(fill=tk.X, pady=5)
            elif mode == 'palette':
                self.frame_palette_param.pack(fill=tk.X, pady=5)
            elif mode == 'median':
                self.frame_median_param.pack(fill=tk.X, pady=5)
            elif mode == 'local_median':
                self.frame_local_param.pack(fill=tk.X, pady=5)
                if self.original_img:
                    self.processed_img = self.original_img.copy()
            elif mode == 'art_brush':
                self.frame_art_brush_param.pack(fill=tk.X, pady=5)
                if self.original_img:
                    self.processed_img = self.original_img.copy()
            elif mode == 'gif_maker':
                self.frame_gif_param.pack(fill=tk.X, pady=5)

        self.root.update_idletasks()
        self.process_image()
        self.update_preview()

    def on_param_change(self, event=None):
        self.lbl_threshold_val.config(text=str(int(self.scale_threshold.get())))
        self.lbl_colors_val.config(text=f"{int(self.scale_colors.get())} 色")
        
        k_size = int(self.scale_kernel.get())
        if k_size % 2 == 0:
            k_size += 1
        self.lbl_kernel_val.config(text=f"{k_size} x {k_size}")
        self.lbl_brush_val.config(text=f"{int(self.scale_brush.get())} px")
        self.lbl_art_size_val.config(text=f"{int(self.scale_art_size.get())} px")
        self.lbl_gif_duration_val.config(text=f"{int(self.scale_gif_duration.get())} ms")
        
        if self.mode_var.get() != 'gif_maker':
            self.process_image()
            self.update_preview()

    def update_preview(self):
        mode = self.mode_var.get()
        if mode == 'gif_maker':
            if self.gif_frames and self.gif_anim_id is None:
                self.play_gif_preview()
            return

        if self.original_img is None:
            return

        try:
            if mode == 'laplacian':
                # 依據外框 LabelFrame 的固定大小計算縮放，不依賴會被撐開的 Label
                box_width = max(self.frame_lap_a.winfo_width() - 16, 150)
                box_height = max(self.frame_lap_a.winfo_height() - 30, 150)

                if self.laplacian_a and self.laplacian_b and self.laplacian_c:
                    a_resized, _, _, _ = self._resize_aspect_ratio(self.laplacian_a, box_width, box_height)
                    b_resized, _, _, _ = self._resize_aspect_ratio(self.laplacian_b, box_width, box_height)
                    c_resized, _, _, _ = self._resize_aspect_ratio(self.laplacian_c, box_width, box_height)

                    self.tk_lap_a = ImageTk.PhotoImage(a_resized, master=self.root)
                    self.tk_lap_b = ImageTk.PhotoImage(b_resized, master=self.root)
                    self.tk_lap_c = ImageTk.PhotoImage(c_resized, master=self.root)

                    self.lbl_lap_a.config(image=self.tk_lap_a, text="")
                    self.lbl_lap_b.config(image=self.tk_lap_b, text="")
                    self.lbl_lap_c.config(image=self.tk_lap_c, text="")
            else:
                box_width = max(self.frame_orig.winfo_width() - 16, 180)
                box_height = max(self.frame_orig.winfo_height() - 30, 180)

                orig_resized, _, _, _ = self._resize_aspect_ratio(self.original_img, box_width, box_height)
                self.tk_orig_image = ImageTk.PhotoImage(orig_resized, master=self.root)
                self.lbl_orig_preview.config(image=self.tk_orig_image, text="")

                if self.processed_img:
                    proc_resized, scale, ox, oy = self._resize_aspect_ratio(self.processed_img, box_width, box_height)
                    self.preview_scale = scale
                    self.offset_x = ox
                    self.offset_y = oy

                    self.tk_proc_image = ImageTk.PhotoImage(proc_resized, master=self.root)
                    self.lbl_proc_preview.config(image=self.tk_proc_image, text="")
        except Exception as e:
            print(f"預覽更新失敗: {e}")

    def _resize_aspect_ratio(self, img, max_w, max_h):
        w, h = img.size
        ratio = min(max_w / w, max_h / h)
        new_w = max(1, int(w * ratio))
        new_h = max(1, int(h * ratio))

        offset_x = (max_w - new_w) // 2
        offset_y = (max_h - new_h) // 2

        resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        return resized_img, ratio, offset_x, offset_y

    def on_resize(self, event):
        """【關鍵修正 2】只有當主視窗寬度或高度真正改變時，才重新計算預覽比例"""
        if event.widget == self.root:
            if event.width != self.last_win_w or event.height != self.last_win_h:
                self.last_win_w = event.width
                self.last_win_h = event.height
                self.update_preview()

    def save_image(self):
        mode = self.mode_var.get()
        base_name = "output"
        if self.src_image_path:
            base_name, _ = os.path.splitext(os.path.basename(self.src_image_path))

        if mode == 'gif_maker':
            if not self.gif_frames:
                messagebox.showwarning("提示", "尚未產生任何 GIF 影格，請先選取多張圖片或產生濾鏡動畫！")
                return

            default_filename = f"{base_name}_animation.gif"
            save_path = filedialog.asksaveasfilename(
                title="匯出 GIF 動畫",
                initialfile=default_filename,
                defaultextension=".gif",
                filetypes=[("GIF 動畫檔", "*.gif")]
            )

            if save_path:
                try:
                    duration = int(self.scale_gif_duration.get())
                    self.gif_frames[0].save(
                        save_path,
                        save_all=True,
                        append_images=self.gif_frames[1:],
                        duration=duration,
                        loop=0
                    )
                    messagebox.showinfo("成功", f"GIF 動畫已成功匯出至：\n{save_path}")
                except Exception as e:
                    messagebox.showerror("錯誤", f"儲存 GIF 失敗：\n{e}")

        elif mode == 'laplacian':
            save_dir = filedialog.askdirectory(title="選擇資料夾 (將自動儲存 a, b, c 三張圖片)")
            if save_dir:
                try:
                    path_a = os.path.join(save_dir, f"{base_name}_laplacian_a_origin.png")
                    path_b = os.path.join(save_dir, f"{base_name}_laplacian_b_edge.png")
                    path_c = os.path.join(save_dir, f"{base_name}_laplacian_c_sharpened.png")

                    self.laplacian_a.save(path_a)
                    self.laplacian_b.save(path_b)
                    self.laplacian_c.save(path_c)

                    messagebox.showinfo("成功", f"(a)、(b)、(c) 三張圖片已成功儲存至：\n{save_dir}")
                except Exception as e:
                    messagebox.showerror("錯誤", f"儲存圖片失敗：\n{e}")
        else:
            if self.processed_img is None:
                return

            default_filename = f"{base_name}_{mode}.png"
            save_path = filedialog.asksaveasfilename(
                title="另存新檔",
                initialfile=default_filename,
                filetypes=[("PNG 檔案", "*.png"), ("JPEG 檔案", "*.jpg"), ("所有檔案", "*.*")]
            )

            if save_path:
                try:
                    self.processed_img.save(save_path)
                    messagebox.showinfo("成功", f"檔案已成功儲存至：\n{save_path}")
                except Exception as e:
                    messagebox.showerror("錯誤", f"儲存檔案失敗：\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageConverterApp(root)
    root.mainloop()