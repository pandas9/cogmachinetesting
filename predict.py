# An example of how to convert a given API workflow into its own Replicate model
# Replace predict.py with this file when building your own workflow

import os
import mimetypes
import json
import shutil
from typing import List
from cog import BasePredictor, Input, Path
from comfyui import ComfyUI
from cog_model_helpers import optimise_images
from cog_model_helpers import seed as seed_helper

OUTPUT_DIR = "/tmp/outputs"
INPUT_DIR = "/tmp/inputs"
COMFYUI_TEMP_OUTPUT_DIR = "ComfyUI/temp"
ALL_DIRECTORIES = [OUTPUT_DIR, INPUT_DIR, COMFYUI_TEMP_OUTPUT_DIR]

ASPECT_RATIOS = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "21:9": (1536, 640),
    "3:2": (1216, 832),
    "2:3": (832, 1216),
    "4:5": (896, 1088),
    "5:4": (1088, 896),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
    "9:16": (768, 1344),
    "9:21": (640, 1536),
}

mimetypes.add_type("image/webp", ".webp")

# Save your example JSON to the same directory as predict.py
api_json_file = "workflow_api.json"

# Force HF offline
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

class Predictor(BasePredictor):
    def setup(self):
        self.comfyUI = ComfyUI("127.0.0.1:8188")
        self.comfyUI.start_server(OUTPUT_DIR, INPUT_DIR)

        # Give a list of weights filenames to download during setup
        with open(api_json_file, "r") as file:
            workflow = json.loads(file.read())

        # doesn't work model stays same even after update_workflow
        #model = workflow["738"]["inputs"]["unet_name"]

        custom_models = []

        self.comfyUI.handle_weights(
            workflow,
            weights_to_download=[],
            custom_models=custom_models,
        )

    def filename_with_extension(self, input_file, prefix):
        extension = os.path.splitext(input_file.name)[1]
        return f"{prefix}{extension}"

    def handle_input_file(
        self,
        input_file: Path,
        filename: str = "image.png",
    ):
        shutil.copy(input_file, os.path.join(INPUT_DIR, filename))

    # Update nodes in the JSON workflow to modify your workflow based on the given inputs
    def update_workflow(self, workflow, **kwargs):
        if kwargs['model'] == "test":
            workflow["738"]["inputs"]["unet_name"] = "STOIQOAfroditeFLUXSD_F1DAlpha.safetensors"
        else:
            workflow["738"]["inputs"]["unet_name"] = "STOIQONewrealityFLUXSD_F1DAlpha.safetensors"

        print("====================================")
        print(f"Model: {workflow['738']['inputs']['unet_name']}")
        print("====================================")

        workflow["742"]["inputs"]["steps"] = kwargs["num_inference_steps"]

        # this is for stoiq with lora stack
        workflow["723"]["inputs"]["text"] = kwargs["prompt"]
        workflow["744"]["inputs"]["noise_seed"] = kwargs["seed"]
        workflow["747"]["inputs"]["width"] = ASPECT_RATIOS[kwargs["aspect_ratio"]][0]
        workflow["747"]["inputs"]["height"] = ASPECT_RATIOS[kwargs["aspect_ratio"]][1]

        workflow["731"]["inputs"]["guidance"] = kwargs["guidance_scale"]
        
        if kwargs['add_lora']:
            workflow["751"]['inputs']['switch_1'] = 'On'
            workflow["751"]['inputs']['lora_name_1'] = "scg-anatomy-female-v2.safetensors"
            workflow["751"]['inputs']['model_weight_1'] = kwargs['lora_scale']


    def predict(
        self,
        prompt: str = Input(
            default="",
        ),
        #negative_prompt: str = Input(
        #    description="Things you do not want to see in your image",
        #    default="",
        #),
        #image: Path = Input(
        #    description="An input image",
        #    default=None,
        #),
        aspect_ratio: str = Input(
            description="Aspect ratio for the generated image",
            choices=list(ASPECT_RATIOS.keys()),
            default="1:1"
        ),
        guidance_scale: float = Input(
            description="Guidance for the generated image",
            default=2.5,
            le=10,
            ge=0.1,
        ),
        num_inference_steps: float = Input(
            description="Number of inference steps",
            default=28,
            le=50,
            ge=1,
        ),
        lora_scale: float = Input(
            description="Initial LoRA scale",
            default=0.5,
            le=1,
            ge=-1,
        ),
        model: str = Input(
            description="Model to use",
            choices=["STOIQONewrealityFLUXSD_F1DAlpha", "test"],
            default="STOIQONewrealityFLUXSD_F1DAlpha",
        ),
        add_lora: bool = Input(
            description="Add LoRA to the model",
            default=False,
        ),
        output_format: str = optimise_images.predict_output_format(),
        output_quality: int = optimise_images.predict_output_quality(),
        seed: int = seed_helper.predict_seed(),
        #lora_url: str = Input(
        #    description="Optional LoRA model to use. Give a URL to a HuggingFace .safetensors file, a Replicate .tar file or a CivitAI download link.",
        #    default="",
        #),
        #lora_strength: float = Input(
        #    description="Strength of LoRA model",
        #    default=1,
        #    le=3,
        #    ge=-1,
        #),
    ) -> List[Path]:
        """Run a single prediction on the model"""
        self.comfyUI.cleanup(ALL_DIRECTORIES)

        # Make sure to set the seeds in your workflow
        seed = seed_helper.generate(seed)

        #lora_filename = None
        #if lora_url:
        #    lora_filename = self.download_lora(lora_url)

        #image_filename = None
        #if image:
        #    image_filename = self.filename_with_extension(image, "image")
        #    self.handle_input_file(image, image_filename)

        with open(api_json_file, "r") as file:
            workflow = json.loads(file.read())

        self.update_workflow(
            workflow,
            prompt=prompt,
            #negative_prompt=negative_prompt,
            #image_filename=image_filename,
            seed=seed,
            #lora_filename=lora_filename,
            #lora_strength=lora_strength,
            aspect_ratio=aspect_ratio,
            guidance_scale=guidance_scale,
            lora_scale=lora_scale,
            num_inference_steps=num_inference_steps,
            model=model,
            add_lora=add_lora,
        )

        wf = self.comfyUI.load_workflow(workflow)
        self.comfyUI.connect()
        self.comfyUI.run_workflow(wf)

        return optimise_images.optimise_image_files(
            output_format, output_quality, self.comfyUI.get_files(OUTPUT_DIR)
        )
