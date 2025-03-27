# Copyright 2025 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
import threading
from typing import Dict, Optional, List
import logging
import numpy as np

from dimos.utils.simple_controller import VisualServoingController

# Configure logging
logger = logging.getLogger(__name__)


def calculate_iou(box1, box2):
    """Calculate Intersection over Union between two bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0


class VisualServoing:
    """
    A class that performs visual servoing to track and follow a human target.
    
    The class will use the provided tracking stream to detect people and estimate
    their distance and angle, then use a VisualServoingController to generate
    appropriate velocity commands to track the target.
    """
    
    def __init__(self, tracking_stream=None, max_linear_speed=0.5, max_angular_speed=0.75,
                 desired_distance=1.0, max_lost_frames=20, iou_threshold=0.6):
        """Initialize the visual servoing.
        
        Args:
            tracking_stream: Observable tracking stream (must be already set up)
            max_linear_speed: Maximum linear speed in m/s
            max_angular_speed: Maximum angular speed in rad/s
            desired_distance: Desired distance to maintain from target in meters
            max_lost_frames: Maximum number of frames target can be lost before stopping tracking
            iou_threshold: Minimum IOU threshold to consider bounding boxes as matching
        """
        self.tracking_stream = tracking_stream
        self.max_linear_speed = max_linear_speed
        self.max_angular_speed = max_angular_speed
        self.desired_distance = desired_distance
        self.max_lost_frames = max_lost_frames
        self.iou_threshold = iou_threshold
        
        # Initialize the controller with PID parameters tuned for slow-moving robot
        # Distance PID: (kp, ki, kd, output_limits, integral_limit, deadband, output_deadband)
        distance_pid_params = (
            0.8,    # kp: Moderate proportional gain for smooth approach
            0.2,    # ki: Small integral gain to eliminate steady-state error
            0.1,    # kd: Some damping for smooth motion
            (-self.max_linear_speed, self.max_linear_speed),  # output_limits
            0.5,    # integral_limit: Prevent windup
            0.1,    # deadband: Small deadband for distance control
            0.05,   # output_deadband: Minimum output to overcome friction
        )
        
        # Angle PID: (kp, ki, kd, output_limits, integral_limit, deadband, output_deadband)
        angle_pid_params = (
            0.9,    # kp: Higher proportional gain for responsive turning
            0.1,    # ki: Small integral gain
            0.05,   # kd: Light damping to prevent oscillation
            (-self.max_angular_speed, self.max_angular_speed),  # output_limits
            0.3,    # integral_limit: Prevent windup
            0.05,   # deadband: Small deadband for angle control
            0.1,    # output_deadband: Minimum output to overcome friction
        )
        
        # Initialize the visual servoing controller
        self.controller = VisualServoingController(
            distance_pid_params=distance_pid_params,
            angle_pid_params=angle_pid_params
        )
        
        # Initialize tracking state
        self.last_control_time = time.time()
        self.running = False
        self.current_target = None  # (target_id, bbox)
        self.target_lost_frames = 0
        
        # Stream subscription management
        self.subscription = None
        self.latest_result = None
        self.result_lock = threading.Lock()
        self.stop_event = threading.Event()
        
        # Subscribe to the tracking stream
        self._subscribe_to_tracking_stream()
        
    def start_tracking(self, bbox: Optional[list] = None, timeout_wait_for_target: float = 10.0) -> bool:
        """
        Start tracking a human target using visual servoing.
        
        Args:
            bbox: Optional bounding box [x1, y1, x2, y2] of target to track.
                 If provided, finds the closest target by IOU and tracks it.
                 If None, tracks the closest person in the image stream.
            timeout_wait_for_target: Maximum time in seconds to wait for a target to appear.
                 
        Returns:
            bool: True if tracking was successfully started, False otherwise
        """
        if self.tracking_stream is None:
            self.running = False
            return False
        
        # Get the latest frame and targets from person tracker
        try:
            # Get the result of the person tracking stream
            result = self._get_current_tracking_result()

            if result is None:
                logger.warning("Stream error, no targets found")
                return False

            targets = result.get("targets")
            
            # If bbox is provided, find matching target based on IOU
            if bbox is not None and not self.running:
                # Find the target with highest IOU to the provided bbox
                best_target = self._find_best_target_by_iou(bbox, targets)
            # If no bbox is provided, find the closest person
            elif not self.running:
                if timeout_wait_for_target > 0.0 and len(targets) == 0:
                    # Wait for target to appear
                    start_time = time.time()
                    while time.time() - start_time < timeout_wait_for_target:
                        time.sleep(0.2)
                        result = self._get_current_tracking_result()
                        targets = result.get("targets")
                        if len(targets) > 0:
                            break
                best_target = self._find_closest_target(targets)
            else:
                # Already tracking
                return True
                
            if best_target:
                # Set as current target and reset lost counter
                target_id = best_target.get("target_id")
                target_bbox = best_target.get("bbox")
                self.current_target = (target_id, target_bbox)
                self.target_lost_frames = 0
                self.running = True
                logger.info(f"Started tracking target ID: {target_id}")
                
                # Get distance and angle and compute control (store as initial control values)
                distance = best_target.get("distance")
                angle = best_target.get("angle")
                self._compute_control(distance, angle)
                return True
            else:
                if bbox is not None:
                    logger.warning("No matching target found using IOU")
                else:
                    logger.warning("No suitable target found for tracking")
                self.running = False
                return False
        except Exception as e:
            logger.error(f"Error starting tracking: {e}")
            self.running = False
            return False
    
    def updateTracking(self) -> Dict[str, any]:
        """
        Update tracking of current target.
        
        Returns:
            Dict with linear_vel, angular_vel, and running state
        """
        if not self.running or self.current_target is None:
            self.running = False
            return {"linear_vel": 0.0, "angular_vel": 0.0}
        
        # Get the latest tracking result
        result = self._get_current_tracking_result()
        
        # Get targets from result
        targets = result.get("targets")
        
        # Try to find current target by ID or IOU
        current_target_id, current_bbox = self.current_target
        target_found = False
        
        # First try to find by ID
        for target in targets:
            if target.get("target_id") == current_target_id:
                # Found by ID, update bbox
                self.current_target = (current_target_id, target.get("bbox"))
                self.target_lost_frames = 0
                target_found = True
                
                # Compute control
                distance = target.get("distance")
                angle = target.get("angle")
                control = self._compute_control(distance, angle)
                return control
        
        # If not found by ID, try to find by IOU
        if not target_found and current_bbox is not None:
            best_target = self._find_best_target_by_iou(current_bbox, targets)
            if best_target:
                # Update target
                new_id = best_target.get("target_id")
                new_bbox = best_target.get("bbox")
                self.current_target = (new_id, new_bbox)
                self.target_lost_frames = 0
                logger.info(f"Target ID updated: {current_target_id} -> {new_id}")
                
                # Compute control
                distance = best_target.get("distance")
                angle = best_target.get("angle")
                control = self._compute_control(distance, angle)
                return control
        
        # Target not found, increment lost counter
        if not target_found:
            self.target_lost_frames += 1
            logger.warning(f"Target lost: frame {self.target_lost_frames}/{self.max_lost_frames}")
            
            # Check if target is lost for too many frames
            if self.target_lost_frames >= self.max_lost_frames:
                logger.info("Target lost for too many frames, stopping tracking")
                self.stop_tracking()
                return {"linear_vel": 0.0, "angular_vel": 0.0, "running": False}
        
        return {"linear_vel": 0.0, "angular_vel": 0.0}
            
        
    def _compute_control(self, distance: float, angle: float) -> Dict[str, float]:
        """
        Compute control commands based on measured distance and angle.
        
        Args:
            distance: Measured distance to target in meters
            angle: Measured angle to target in radians
            
        Returns:
            Dict with linear_vel and angular_vel keys
        """
        current_time = time.time()
        dt = current_time - self.last_control_time
        self.last_control_time = current_time
        
        # Compute control with visual servoing controller
        linear_vel, angular_vel = self.controller.compute_control(
            measured_distance=distance,
            measured_angle=angle,
            desired_distance=self.desired_distance,
            desired_angle=0.0,  # Keep target centered
            dt=dt
        )
        
        # Log control values for debugging
        logger.debug(f"Distance: {distance:.2f}m, Angle: {np.rad2deg(angle):.1f}°")
        logger.debug(f"Control: linear={linear_vel:.2f}m/s, angular={angular_vel:.2f}rad/s")
        
        return {
            "linear_vel": linear_vel,
            "angular_vel": angular_vel
        }
    
    def _find_best_target_by_iou(self, bbox: List[float], targets: List[Dict]) -> Optional[Dict]:
        """
        Find the target with highest IOU to the given bbox.
        
        Args:
            bbox: Bounding box to match [x1, y1, x2, y2]
            targets: List of target dictionaries
            
        Returns:
            Best matching target or None if no match found
        """
        if not targets:
            return None
        
        best_iou = self.iou_threshold
        best_target = None
        
        for target in targets:
            target_bbox = target.get("bbox")
            if target_bbox is None:
                continue
                
            iou = calculate_iou(bbox, target_bbox)
            if iou > best_iou:
                best_iou = iou
                best_target = target
        
        return best_target
    
    def _find_closest_target(self, targets: List[Dict]) -> Optional[Dict]:
        """
        Find the target with shortest distance to the camera.
        
        Args:
            targets: List of target dictionaries
            
        Returns:
            The closest target or None if no targets available
        """
        if not targets:
            return None
        
        closest_target = None
        min_distance = float('inf')
        
        for target in targets:
            distance = target.get("distance")
            if distance is not None and distance < min_distance:
                min_distance = distance
                closest_target = target
        
        return closest_target
    
    def _subscribe_to_tracking_stream(self):
        """
        Subscribe to the already set up tracking stream.
        """
        if self.tracking_stream is None:
            logger.warning("No tracking stream provided to subscribe to")
            return
            
        try:
            # Set up subscription to process frames
            self.subscription = self.tracking_stream.subscribe(
                on_next=self._on_tracking_result,
                on_error=self._on_tracking_error,
                on_completed=self._on_tracking_completed
            )
            
            logger.info("Subscribed to tracking stream successfully")
        except Exception as e:
            logger.error(f"Error subscribing to tracking stream: {e}")
    
    def _on_tracking_result(self, result):
        """
        Callback for tracking stream results.
        
        This updates the latest result for use by _get_current_tracking_result.
        
        Args:
            result: The result from the tracking stream
        """
        if self.stop_event.is_set():
            return
            
        # Update the latest result
        with self.result_lock:
            self.latest_result = result
    
    def _on_tracking_error(self, error):
        """
        Callback for tracking stream errors.
        
        Args:
            error: The error from the tracking stream
        """
        logger.error(f"Tracking stream error: {error}")
        self.stop_event.set()
    
    def _on_tracking_completed(self):
        """Callback for tracking stream completion."""
        logger.info("Tracking stream completed")
        self.stop_event.set()
    
    def _get_current_tracking_result(self) -> Optional[Dict]:
        """
        Get the current tracking result.
        
        Returns the latest result cached from the tracking stream subscription.
        
        Returns:
            Dict with 'frame' and 'targets' or None if not available
        """
        # Return the latest cached result
        with self.result_lock:
            return self.latest_result

    def stop_tracking(self):
        """Stop tracking and reset controller state."""
        self.running = False
        self.current_target = None
        self.target_lost_frames = 0
        return {"linear_vel": 0.0, "angular_vel": 0.0, "running": False}
    
    def cleanup(self):
        """Clean up all resources used by the visual servoing."""
        self.stop_event.set()
        if self.subscription:
            self.subscription.dispose()
            self.subscription = None
