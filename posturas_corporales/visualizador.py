"""
python visualizador_v2.py .mp4 .csv
python visualizador_v2.py ./videos_limpios/.mp4 ./csvs/.csv
"""
import cv2
import pandas as pd
import numpy as np
import argparse
import os
import sys

class LandmarkVideoViewer:
    def __init__(self, video_path, csv_path):
        """
        Visualizador simple de landmarks - solo lee video y CSV
        
        Args:
            video_path: Ruta del video original
            csv_path: Ruta del archivo CSV con landmarks pre-procesados
        """
        self.video_path = video_path
        self.csv_path = csv_path

        # Cargar video
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"❌ No se pudo abrir el video: {video_path}")
        
        # Propiedades del video
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Cargar landmarks del CSV
        try:
            self.landmarks_df = pd.read_csv(csv_path)
            print(f"✅ CSV cargado: {len(self.landmarks_df)} frames de landmarks")
        except Exception as e:
            raise ValueError(f"❌ Error al cargar CSV: {e}")
        
        # Nombres de los 17 keypoints
        self.keypoint_names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        # Colores por tipo de keypoint
        self.keypoint_colors = {
            # Cara - Amarillo
            'nose': (0, 255, 255), 'left_eye': (0, 255, 255), 'right_eye': (0, 255, 255),
            'left_ear': (0, 255, 255), 'right_ear': (0, 255, 255),
            
            # Torso - Verde
            'left_shoulder': (0, 255, 0), 'right_shoulder': (0, 255, 0),
            'left_hip': (0, 255, 0), 'right_hip': (0, 255, 0),
            
            # Brazos - Azul
            'left_elbow': (255, 0, 0), 'right_elbow': (255, 0, 0),
            'left_wrist': (255, 0, 0), 'right_wrist': (255, 0, 0),
            
            # Piernas - Magenta
            'left_knee': (255, 0, 255), 'right_knee': (255, 0, 255),
            'left_ankle': (255, 0, 255), 'right_ankle': (255, 0, 255)
        }
        
        # Conexiones para dibujar esqueleto
        self.skeleton_connections = [
            # Cara
            ('left_eye', 'right_eye'), ('left_eye', 'nose'), ('right_eye', 'nose'),
            ('left_eye', 'left_ear'), ('right_eye', 'right_ear'),
            
            # Torso
            ('left_shoulder', 'right_shoulder'), ('left_shoulder', 'left_hip'),
            ('right_shoulder', 'right_hip'), ('left_hip', 'right_hip'),
            
            # Brazos
            ('left_shoulder', 'left_elbow'), ('left_elbow', 'left_wrist'),
            ('right_shoulder', 'right_elbow'), ('right_elbow', 'right_wrist'),
            
            # Piernas
            ('left_hip', 'left_knee'), ('left_knee', 'left_ankle'),
            ('right_hip', 'right_knee'), ('right_knee', 'right_ankle')
        ]
        
        # Control de reproducción
        self.current_frame = 0
        self.is_playing = True
        self.playback_speed = 1.0
        
        print(f"🎬 Video: {self.width}x{self.height}, {self.fps}FPS, {self.total_frames} frames")
    
    def get_landmarks_for_frame(self, frame_idx):
        """
        Obtiene los landmarks del CSV para un frame específico
        
        Args:
            frame_idx: Índice del frame
            
        Returns:
            Dictionary con keypoints válidos: {nombre: (x, y, conf)}
        """
        if frame_idx >= len(self.landmarks_df):
            return {}
        
        landmarks_row = self.landmarks_df.iloc[frame_idx]
        valid_keypoints = {}
        
        for kp_name in self.keypoint_names:
            x_col = f'{kp_name}_x'
            y_col = f'{kp_name}_y'
            conf_col = f'{kp_name}_confidence'
            
            # Verificar que las columnas existen en el CSV
            if all(col in landmarks_row.index for col in [x_col, y_col, conf_col]):
                x = landmarks_row[x_col]
                y = landmarks_row[y_col]
                conf = landmarks_row[conf_col]
                
                # Solo incluir keypoints válidos (no NaN y con confianza mínima)
                if not (pd.isna(x) or pd.isna(y) or pd.isna(conf)) and conf > 0.3:
                    valid_keypoints[kp_name] = (int(x), int(y), float(conf))
        
        return valid_keypoints
    
    def draw_landmarks(self, frame, keypoints):
        """
        Dibuja landmarks y esqueleto en el frame
        
        Args:
            frame: Frame de video
            keypoints: Dict con keypoints válidos
            
        Returns:
            Frame con landmarks dibujados
        """
        if not keypoints:
            return frame
        
        result_frame = frame.copy()
        
        # 1. Dibujar conexiones del esqueleto
        for connection in self.skeleton_connections:
            kp1_name, kp2_name = connection
            
            if kp1_name in keypoints and kp2_name in keypoints:
                pt1 = keypoints[kp1_name][:2]  # (x, y)
                pt2 = keypoints[kp2_name][:2]  # (x, y)
                
                # Color basado en el primer keypoint
                line_color = self.keypoint_colors[kp1_name]
                
                # Dibujar línea del esqueleto
                cv2.line(result_frame, pt1, pt2, line_color, 2)
        
        # 2. Dibujar keypoints individuales
        for kp_name, (x, y, conf) in keypoints.items():
            color = self.keypoint_colors[kp_name]
            
            # Tamaño del punto basado en importancia
            if kp_name in ['nose', 'left_shoulder', 'right_shoulder']:
                radius = 6  # Puntos importantes más grandes
            else:
                radius = 4
            
            # Dibujar keypoint con borde blanco
            cv2.circle(result_frame, (x, y), radius, color, -1)
            cv2.circle(result_frame, (x, y), radius + 1, (255, 255, 255), 2)
            
            # Mostrar confianza para puntos importantes
            if conf > 0.8 and kp_name in ['nose']:
                cv2.putText(result_frame, f'{conf:.2f}', (x + 10, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        return result_frame
    
    def draw_interface(self, frame):
        """
        Dibuja la interfaz de usuario sobre el frame
        """
        # Overlay semi-transparente para información
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (600, 130), (0, 0, 0), -1)
        frame = cv2.addWeighted(frame, 0.75, overlay, 0.25, 0)
        
        # Información del frame actual
        frame_info = f"Frame: {self.current_frame + 1} / {self.total_frames}"
        time_current = self.current_frame / self.fps if self.fps > 0 else 0
        time_total = self.total_frames / self.fps if self.fps > 0 else 0
        time_info = f"Tiempo: {time_current:.2f}s / {time_total:.2f}s"
        speed_info = f"Velocidad: {self.playback_speed:.2f}x"
        status = "▶️ REPRODUCIENDO" if self.is_playing else "⏸️ PAUSADO"
        
        # Dibujar textos
        texts = [frame_info, time_info, speed_info, status]
        for i, text in enumerate(texts):
            y_pos = 35 + (i * 25)
            cv2.putText(frame, text, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Barra de progreso
        bar_x, bar_y = 20, self.height - 60
        bar_width, bar_height = self.width - 40, 15
        
        # Fondo de la barra
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (50, 50, 50), -1)
        
        # Progreso actual
        if self.total_frames > 0:
            progress = int((self.current_frame / self.total_frames) * bar_width)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + progress, bar_y + bar_height), (0, 255, 0), -1)
        
        # Controles en la parte inferior
        controls = "CONTROLES: [ESPACIO]=Pausa  [A/D]=Frame±1  [S/W]=Velocidad±  [R]=Reiniciar  [Q]=Salir"
        cv2.putText(frame, controls, (20, self.height - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def handle_keypress(self, key):
        """
        Maneja las teclas presionadas
        
        Returns:
            False si debe salir, True para continuar
        """
        if key == 32:  # ESPACIO
            self.is_playing = not self.is_playing
            status = "▶️ REPRODUCIENDO" if self.is_playing else "⏸️ PAUSADO"
            print(f"{status}")
            
        elif key == ord('a') or key == ord('A'):  # Frame anterior
            self.current_frame = max(0, self.current_frame - 1)
            self.is_playing = False
            print(f"⬅️ Frame: {self.current_frame + 1}")
            
        elif key == ord('d') or key == ord('D'):  # Frame siguiente
            self.current_frame = min(self.total_frames - 1, self.current_frame + 1)
            self.is_playing = False
            print(f"➡️ Frame: {self.current_frame + 1}")
            
        elif key == ord('s') or key == ord('S'):  # Velocidad -
            self.playback_speed = max(0.25, self.playback_speed - 0.25)
            print(f"🐌 Velocidad: {self.playback_speed:.2f}x")
            
        elif key == ord('w') or key == ord('W'):  # Velocidad +
            self.playback_speed = min(4.0, self.playback_speed + 0.25)
            print(f"⚡ Velocidad: {self.playback_speed:.2f}x")
            
        elif key == ord('r') or key == ord('R'):  # Reiniciar
            self.current_frame = 0
            self.is_playing = True
            print("🔄 Reiniciando")
            
        elif key == ord('q') or key == ord('Q') or key == 27:  # Salir
            return False
            
        return True
    
    def run(self):
        """
        Ejecuta el visualizador
        """
        print("\n🎬 VISUALIZADOR DE LANDMARKS")
        print("=" * 50)
        print("📋 CONTROLES:")
        print("  ESPACIO    - Pausar/Reproducir")
        print("  A / D      - Frame anterior/siguiente")  
        print("  S / W      - Velocidad - / +")
        print("  R          - Reiniciar video")
        print("  Q / ESC    - Salir")
        print("=" * 50)
        print("🎯 Visualizando landmarks del CSV sobre video original")
        print("🎨 Colores: 🟡Cara 🟢Torso 🔵Brazos 🟣Piernas")
        
        try:
            while True:
                # Leer frame actual del video
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
                ret, frame = self.cap.read()
                
                if not ret:
                    print("📽️ Fin del video")
                    self.current_frame = 0  # Reiniciar para loop
                    continue
                
                # Obtener landmarks del CSV para este frame
                keypoints = self.get_landmarks_for_frame(self.current_frame)
                
                # Dibujar landmarks sobre el frame
                frame_with_landmarks = self.draw_landmarks(frame, keypoints)
                
                # Dibujar interfaz de usuario
                final_frame = self.draw_interface(frame_with_landmarks)
                
                # Mostrar resultado
                cv2.imshow('Landmarks Video Viewer - Presiona Q para salir', final_frame)
                
                # Control de timing y teclas
                if self.is_playing:
                    # Calcular delay basado en FPS y velocidad
                    delay = max(1, int(1000 / (self.fps * self.playback_speed)))
                    key = cv2.waitKey(delay) & 0xFF
                    
                    # Avanzar frame
                    self.current_frame += 1
                    if self.current_frame >= self.total_frames:
                        self.current_frame = 0  # Loop automático
                else:
                    # Pausado - esperar tecla
                    key = cv2.waitKey(0) & 0xFF
                
                # Procesar teclas
                if not self.handle_keypress(key):
                    break
                    
        except KeyboardInterrupt:
            print("\n⏹️ Interrumpido por usuario")
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
            print("👋 Visualizador cerrado")

def main():
    parser = argparse.ArgumentParser(description='Visualizador simple de landmarks en video')
    parser.add_argument('video_path', help='Ruta del video original')
    parser.add_argument('csv_path', help='Ruta del CSV con landmarks')
    
    args = parser.parse_args()
    
    # Verificar archivos
    if not os.path.exists(args.video_path):
        print(f"❌ Video no encontrado: {args.video_path}")
        return
        
    if not os.path.exists(args.csv_path):
        print(f"❌ CSV no encontrado: {args.csv_path}")
        return
    
    try:
        # Crear y ejecutar visualizador
        viewer = LandmarkVideoViewer(args.video_path, args.csv_path)
        viewer.run()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("📖 USO:")
        print("  python visualizador.py <video.mp4> <landmarks.csv>")
        print("\n📋 EJEMPLO:")
        print("  python visualizador.py penal_futbol.mp4 landmarks_jugador_5.csv")
        print("\n💡 DESCRIPCIÓN:")
        print("  Visualiza landmarks guardados en CSV sobre el video original")
        print("  No procesa nada, solo muestra los datos ya calculados")
    else:
        main()